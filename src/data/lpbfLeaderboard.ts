/// <reference types="vite/client" />
/**
 * Typed, read-only loader for the Python-generated open LPBF screening-benchmark leaderboard record
 * (docs/LPBF_LEADERBOARD_<date>.json, schema "lpbf-leaderboard-1", written by python/tools/lpbf_benchmark_score.py).
 *
 * Python is the result authority: every number shown comes from that JSON. This module validates shape and honesty
 * flags and offers pure sorting/grouping helpers; it computes no physics and no statistics, and it never builds one
 * cross-material rank. Screening benchmark of published single tracks, not validation.
 *
 * Vite inlines the newest (by file name) docs/LPBF_LEADERBOARD_*.json. When none is committed the glob is empty and
 * the panel shows an honest "no record committed yet" state. Outside Vite (tests under tsx) the glob is unavailable
 * and the record is treated as absent; tests pass documents to the panel explicitly.
 */

export const LPBF_LEADERBOARD_SCHEMA = "lpbf-leaderboard-1";
export const ENTRY_KINDS = ["built-in-kernel", "local-submission"] as const;
export type EntryKind = (typeof ENTRY_KINDS)[number];
export const KIND_LABEL: Readonly<Record<EntryKind, string>> = {
  "built-in-kernel": "built-in kernel",
  "local-submission": "local submission",
};
export const CELL_STATUSES = ["scored", "excluded-trained-on"] as const;
export type CellStatus = (typeof CELL_STATUSES)[number];

export interface LeaderboardCoverage {
  readonly k: number;
  readonly n: number;
  readonly coverage: number | null;
  readonly wilson95: readonly [number, number] | null;
}

export interface LeaderboardCell {
  readonly material: string;
  readonly quantity: "width" | "depth";
  readonly heldOutSource: string;
  readonly status: CellStatus;
  readonly nRows: number;
  readonly nSets: number;
  readonly reason?: string;
  readonly nResolved?: number;
  readonly unresolved?: number;
  readonly mapePct?: number | null;
  readonly meanAbsLn?: number | null;
  readonly mapeUnresolvedAsFailPct?: number | null;
  readonly skill?: number | null;
  readonly skillCi95?: readonly [number, number] | null;
  readonly coverage90?: LeaderboardCoverage | null;
}

export interface LeaderboardEntry {
  readonly id: string;
  readonly kind: EntryKind;
  readonly name: string;
  readonly version: string;
  readonly author: string;
  readonly description: string;
  readonly url: string;
  readonly trainedOnSources: readonly string[];
  readonly provenance: {
    readonly manifestSha256: string;
    readonly implementationHash: string;
    readonly baselineKernel: string;
    readonly kernel?: string;
    readonly predictionsSha256?: string;
    readonly submissionCsvSha256?: string;
    readonly metaSha256?: string;
  };
  readonly cells: readonly LeaderboardCell[];
  readonly sentinels: readonly LeaderboardCell[];
}

export interface LpbfLeaderboardDocument {
  readonly schema: typeof LPBF_LEADERBOARD_SCHEMA;
  readonly generatedAt: string;
  readonly implementationHash: string;
  readonly configSha256: string;
  readonly manifestSha256: string;
  readonly evidence: {
    readonly kind: "screening-only";
    readonly statement: string;
    readonly experimentalValidation: false;
    readonly labelPromotionProposed: string;
  };
  readonly honesty: string;
  readonly calibratedRung: { readonly enabledCells: number; readonly note: string };
  readonly entries: readonly LeaderboardEntry[];
}

function fail(reason: string): never {
  throw new Error(`lpbf leaderboard record rejected: ${reason}`);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function finiteOrNull(value: unknown): boolean {
  return value === null || value === undefined || (typeof value === "number" && Number.isFinite(value));
}

function str(value: unknown, where: string, allowEmpty = false): string {
  if (typeof value !== "string" || (!allowEmpty && value.length === 0)) fail(`${where} is not a${allowEmpty ? "" : " non-empty"} string`);
  return value;
}

function checkCells(value: unknown, where: string): void {
  if (!Array.isArray(value)) fail(`${where} is not an array`);
  for (const [i, c] of value.entries()) {
    const w = `${where}[${i}]`;
    if (!isRecord(c)) fail(`${w} is not an object`);
    str(c.material, `${w}.material`);
    str(c.heldOutSource, `${w}.heldOutSource`);
    if (c.quantity !== "width" && c.quantity !== "depth") fail(`${w}.quantity`);
    if (!CELL_STATUSES.includes(c.status as CellStatus)) fail(`${w}.status ${String(c.status)}`);
    for (const f of ["nRows", "nSets"]) if (typeof c[f] !== "number" || !Number.isFinite(c[f])) fail(`${w}.${f}`);
    for (const f of ["mapePct", "meanAbsLn", "mapeUnresolvedAsFailPct", "skill"]) if (!finiteOrNull(c[f])) fail(`${w}.${f} is not finite`);
    if (c.status === "scored" && typeof c.unresolved !== "number") fail(`${w}.unresolved is missing`);
    if (c.skillCi95 !== null && c.skillCi95 !== undefined) {
      if (!Array.isArray(c.skillCi95) || c.skillCi95.length !== 2 || !c.skillCi95.every((x) => typeof x === "number" && Number.isFinite(x))) fail(`${w}.skillCi95`);
    }
  }
}

/** Validates a parsed leaderboard record; throws (loudly) on any malformed or dishonest field. */
export function checkedLeaderboard(raw: unknown): LpbfLeaderboardDocument {
  if (!isRecord(raw)) fail("not an object");
  if (raw.schema !== LPBF_LEADERBOARD_SCHEMA) fail(`schema ${String(raw.schema)}`);
  str(raw.generatedAt, "generatedAt");
  str(raw.implementationHash, "implementationHash");
  str(raw.configSha256, "configSha256");
  str(raw.manifestSha256, "manifestSha256");
  str(raw.honesty, "honesty");
  const ev = raw.evidence;
  if (!isRecord(ev)) fail("evidence is not an object");
  if (ev.kind !== "screening-only") fail("evidence.kind must be screening-only");
  if (ev.experimentalValidation !== false) fail("evidence.experimentalValidation must be false");
  str(ev.statement, "evidence.statement");
  if (!isRecord(raw.calibratedRung) || typeof raw.calibratedRung.enabledCells !== "number") fail("calibratedRung is malformed");
  if (!Array.isArray(raw.entries)) fail("entries is not an array");
  const ids = new Set<string>();
  for (const [i, e] of raw.entries.entries()) {
    const w = `entries[${i}]`;
    if (!isRecord(e)) fail(`${w} is not an object`);
    const id = str(e.id, `${w}.id`);
    if (ids.has(id)) fail(`duplicate entry id ${id}`);
    ids.add(id);
    if (!ENTRY_KINDS.includes(e.kind as EntryKind)) fail(`${w}.kind ${String(e.kind)}`);
    str(e.name, `${w}.name`);
    str(e.version, `${w}.version`);
    str(e.author, `${w}.author`);
    str(e.description, `${w}.description`, true);
    str(e.url, `${w}.url`, true);
    if (!Array.isArray(e.trainedOnSources)) fail(`${w}.trainedOnSources`);
    if (!isRecord(e.provenance)) fail(`${w}.provenance`);
    str(e.provenance.manifestSha256, `${w}.provenance.manifestSha256`);
    str(e.provenance.implementationHash, `${w}.provenance.implementationHash`);
    checkCells(e.cells, `${w}.cells`);
    checkCells(e.sentinels, `${w}.sentinels`);
  }
  return raw as unknown as LpbfLeaderboardDocument;
}

let modules: Record<string, unknown> = {};
try {
  modules = import.meta.glob("../../docs/LPBF_LEADERBOARD_*.json", { eager: true, import: "default" });
} catch {
  modules = {};
}

const newestKey = Object.keys(modules).sort().at(-1);

/** null when no record is committed; throws (loudly) when a committed record is malformed. */
export const COMMITTED_LEADERBOARD: LpbfLeaderboardDocument | null =
  newestKey === undefined ? null : checkedLeaderboard(modules[newestKey]);

// ---------------------------------------------------------------------------------------------
// pure display helpers (no statistics)
// ---------------------------------------------------------------------------------------------
export interface LeaderboardRow {
  readonly key: string;
  readonly entryId: string;
  readonly entryName: string;
  readonly entryVersion: string;
  readonly author: string;
  readonly description: string;
  readonly url: string;
  readonly kind: EntryKind;
  readonly isBaseline: boolean;
  readonly sha: string;
  readonly trainedOnSources: readonly string[];
  readonly cell: LeaderboardCell;
}

export interface LeaderboardGroup {
  readonly material: string;
  readonly quantity: "width" | "depth";
  readonly rows: readonly LeaderboardRow[];
}

export function provenanceSha(entry: LeaderboardEntry): string {
  const p = entry.provenance;
  return p.predictionsSha256 ?? p.submissionCsvSha256 ?? p.manifestSha256;
}

/** One group per (material, quantity); never a cross-material combination. */
export function groupRows(doc: LpbfLeaderboardDocument, block: "cells" | "sentinels" = "cells"): LeaderboardGroup[] {
  const groups = new Map<string, { material: string; quantity: "width" | "depth"; rows: LeaderboardRow[] }>();
  for (const e of doc.entries) {
    const baseline = e.provenance.kernel !== undefined && e.provenance.kernel === e.provenance.baselineKernel;
    for (const cell of e[block]) {
      const k = `${cell.material}|${cell.quantity}`;
      const g = groups.get(k) ?? { material: cell.material, quantity: cell.quantity, rows: [] };
      g.rows.push({
        key: `${e.id}|${cell.heldOutSource}`, entryId: e.id, entryName: e.name, entryVersion: e.version, author: e.author,
        description: e.description, url: e.url, kind: e.kind, isBaseline: baseline, sha: provenanceSha(e),
        trainedOnSources: e.trainedOnSources, cell,
      });
      groups.set(k, g);
    }
  }
  return [...groups.values()].sort((a, b) => a.material.localeCompare(b.material) || (a.quantity === b.quantity ? 0 : a.quantity === "width" ? -1 : 1));
}

export const SORT_KEYS = ["entry", "kind", "heldOutSource", "nRows", "mapePct", "skill", "coverage", "unresolved"] as const;
export type SortKey = (typeof SORT_KEYS)[number];
export type SortDir = "asc" | "desc";
export interface SortState { readonly key: SortKey; readonly dir: SortDir }
export const DEFAULT_SORT: SortState = { key: "mapePct", dir: "asc" };

/** Clicking the active header flips the direction; a new header starts ascending. */
export function nextSort(state: SortState, key: SortKey): SortState {
  return state.key === key ? { key, dir: state.dir === "asc" ? "desc" : "asc" } : { key, dir: "asc" };
}

function sortValue(row: LeaderboardRow, key: SortKey): number | string | null {
  const c = row.cell;
  switch (key) {
    case "entry": return row.entryName.toLowerCase();
    case "kind": return row.kind;
    case "heldOutSource": return c.heldOutSource;
    case "nRows": return c.nRows;
    case "mapePct": return c.mapePct ?? null;
    case "skill": return c.skill ?? null;
    case "coverage": return c.coverage90?.coverage ?? null;
    case "unresolved": return c.unresolved ?? null;
  }
}

/** Stable sort; excluded (trained-on) rows and missing values always stay at the bottom, whatever the direction. */
export function sortRows(rows: readonly LeaderboardRow[], state: SortState): LeaderboardRow[] {
  const sign = state.dir === "asc" ? 1 : -1;
  return [...rows].sort((a, b) => {
    const ea = a.cell.status !== "scored" ? 1 : 0;
    const eb = b.cell.status !== "scored" ? 1 : 0;
    if (ea !== eb) return ea - eb;
    const va = ea ? null : sortValue(a, state.key);
    const vb = eb ? null : sortValue(b, state.key);
    if (va === null && vb !== null) return 1;
    if (vb === null && va !== null) return -1;
    if (va !== null && vb !== null && va !== vb) return (va < vb ? -1 : 1) * sign;
    return a.entryName.localeCompare(b.entryName) || a.cell.heldOutSource.localeCompare(b.cell.heldOutSource);
  });
}

export function fmtFixed(value: number | null | undefined, digits: number): string {
  if (value === null || value === undefined) return "n/a";
  const text = value.toFixed(digits);
  return /^-0(\.0+)?$/.test(text) ? text.slice(1) : text;
}
