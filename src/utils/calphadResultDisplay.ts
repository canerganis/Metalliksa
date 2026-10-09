/**
 * Display rules for pycalphad results added by the calphad-use lane: the unavailable headline, the
 * compiled-model cache state, measured timings, database coverage, the Scheil-Gulliver block and the
 * partition table. Kept apart from calphadDisplay.ts (imported by the shared service, so part of the
 * main bundle); only the CALPHAD Studio imports this module. Nothing here computes or invents a number.
 */

import type { CalphadUnavailable } from "./calphadDisplay";

/** Kinds that mean: no installed, assessed database can answer this alloy system. */
const NO_DATABASE_KINDS = new Set([
  "no-database-covers-elements",
  "database-not-assessed-for-base",
  "elements-missing-from-database",
]);

/** One-line headline of the unavailable state (shown instead of any equilibrium numbers). */
export function calphadUnavailableHeadline(u: CalphadUnavailable): string {
  if (NO_DATABASE_KINDS.has(u.unavailableKind)) return "Unavailable: no thermodynamic database for this system";
  if (u.unavailableKind === "pycalphad-not-installed") return "Unavailable: pycalphad is not installed in the server interpreter";
  if (u.unavailableKind === "engine-unreachable") return "Unavailable: the Python CALPHAD service did not answer";
  if (u.unavailableKind === "pycalphad-equilibrium-failed") return "Unavailable: the pycalphad equilibrium calculation failed";
  return "Unavailable: no CALPHAD result for this request";
}

// ---- calphad-use lane: model cache, timings, coverage, Scheil-Gulliver ----

/** modelCache block of a pycalphad result (python/calphad_model_cache.py stats plus the request's status). */
export interface CalphadModelCacheInfo {
  status?: "cold" | "warm" | "not-cached" | string;
  workspace?: string;
  database?: string;
  databaseSha256?: string | null;
  workspaceBuildMs?: number | null;
  processId?: number;
  workspaceEntries?: number;
  maxWorkspaceEntries?: number;
}

/** "cold" / "warm" in words; never claims a cache state the engine did not report. */
export function formatModelCache(mc: CalphadModelCacheInfo | undefined | null): string {
  if (!mc || !mc.status) return "Model cache: not reported";
  if (mc.status === "warm") return "Models: warm (compiled models reused by this worker)";
  if (mc.status === "cold") {
    const built = typeof mc.workspaceBuildMs === "number" ? `, model construction ${Math.round(mc.workspaceBuildMs)} ms` : "";
    return `Models: cold (built and compiled for this request${built}; code generation is part of the grid time)`;
  }
  return "Models: not cached (pycalphad without the Workspace API)";
}

const TIMING_LABELS: [string, string][] = [
  ["databaseLoad", "database"],
  ["workspaceBuild", "models"],
  ["gridEquilibrium", "grid"],
  ["boundaryRefinement", "liquidus/solidus refinement"],
  ["scheil", "Scheil path"],
  ["total", "total"],
];

/** Measured stage times as reported by the engine, e.g. "grid 414 ms, Scheil path 526 ms, total 1440 ms". */
export function formatTimings(t: Record<string, number> | undefined | null): string | null {
  if (!t) return null;
  const parts = TIMING_LABELS.filter(([k]) => typeof t[k] === "number" && Number.isFinite(t[k])).map(
    ([k, label]) => `${label} ${t[k] < 10 ? t[k].toFixed(1) : Math.round(t[k])} ms`,
  );
  return parts.length ? parts.join(", ") : null;
}

/** One row of systemCoverage from GET /api/python/calphad-databases. */
export interface CalphadSystemCoverage {
  id: string;
  label: string;
  baseElement: string;
  elements: string[];
  status: "covered" | "unavailable";
  databaseId?: string;
  databaseUsed?: string;
  reason?: string;
  missingElements?: string[];
  knownDeviation?: string;
}

export function formatCoverageRow(row: CalphadSystemCoverage): string {
  if (row.status === "covered") {
    return `${row.label}: covered by ${row.databaseUsed ?? row.databaseId} (not validated for this alloy here)`;
  }
  const missing = row.missingElements && row.missingElements.length ? ` (missing: ${row.missingElements.join(", ")})` : "";
  return `${row.label}: unavailable, no thermodynamic database for this system${missing}`;
}

/** Partition row: pycalphad (k of the primary solid phase, null with a reason) or the client screening table. */
export interface CalphadPartitionRow {
  element: string;
  partitionCoefficient_k: number | null;
  partitionCoefficientSource?: string;
  reason?: string | null;
  temperatureC?: number | null;
  primarySolidPhase?: string | null;
  role: string | null;
  matrixFraction_pct?: number;
  precipitateFraction_pct?: number;
}

export function formatPartitionK(k: number | null | undefined): string {
  return typeof k === "number" && Number.isFinite(k) ? `k = ${k.toFixed(3)}` : "Unavailable";
}

export interface CalphadScheilPoint {
  fractionSolid: number;
  temperatureC: number | null;
  liquidCompositions: { [element: string]: number } | null;
  solidCompositions: { [element: string]: number } | null;
  solidPhases?: string[];
}

export interface CalphadScheilBlock {
  status: string;
  reason?: string | null;
  note?: string;
  terminationReason?: string;
  startTemperatureC?: number;
  terminalTemperatureC?: number;
  terminalBracketC?: [number, number] | null;
  remainingLiquidFraction?: number;
  stepC?: number;
  steps?: number;
  phaseAmounts?: Record<string, number>;
  massBalanceMaxAbsError?: number;
  fractionBasis?: string;
  validity?: string;
  evidence?: string;
  /** The solid phase that forms first on the path (partition coefficients refer to it). */
  primarySolidPhase?: string | null;
  /** Caveats for order/disorder model phase names on the path (ordering not checked). */
  phaseNameNotes?: Record<string, string>;
}

export const SCHEIL_COMPUTED = "pycalphad-scheil-gulliver";

/** Summary lines of a Scheil-Gulliver block; only the engine's own numbers, nothing derived here. */
export function scheilSummaryLines(b: CalphadScheilBlock | undefined | null): string[] {
  if (!b) return [];
  if (b.status === "unavailable") return [`Scheil-Gulliver path unavailable: ${b.reason ?? "no reason reported"}.`];
  const lines: string[] = [];
  if (b.status !== SCHEIL_COMPUTED && b.reason) lines.push(`Reason: ${b.reason}.`);
  if (typeof b.startTemperatureC === "number") lines.push(`Start (liquidus bracket, all liquid): ${b.startTemperatureC} °C`);
  const incomplete = b.status !== SCHEIL_COMPUTED;
  if (incomplete) {
    // An incomplete path never claims an end of solidification: it says where it stopped and how much liquid is left.
    const at = typeof b.terminalTemperatureC === "number" ? ` at ${b.terminalTemperatureC} °C` : "";
    const liquid = typeof b.remainingLiquidFraction === "number" ? ` with ${(b.remainingLiquidFraction * 100).toFixed(1)} % liquid` : "";
    lines.push(`Scheil path incomplete: stopped${at}${liquid}${b.terminationReason ? ` (${b.terminationReason})` : ""}. The phase amounts below are partial.`);
  } else if (b.terminalBracketC) {
    lines.push(`End of solidification between ${b.terminalBracketC[0]} and ${b.terminalBracketC[1]} °C (${b.terminationReason}).`);
  } else if (!incomplete && typeof b.terminalTemperatureC === "number") {
    lines.push(`Last step: ${b.terminalTemperatureC} °C (${b.terminationReason}); remaining liquid ${((b.remainingLiquidFraction ?? 0) * 100).toFixed(2)} %.`);
  }
  if (b.phaseAmounts && Object.keys(b.phaseAmounts).length) {
    const phases = Object.entries(b.phaseAmounts)
      .map(([name, f]) => `${withOrderingNote(name, b.phaseNameNotes)} ${(f * 100).toFixed(1)} %`)
      .join(", ");
    lines.push(`${incomplete ? "Solid formed so far" : "Solid formed"} (${b.fractionBasis ?? "mole fraction"}): ${phases}`);
  }
  if (b.primarySolidPhase) lines.push(`Primary solid (first to form): ${withOrderingNote(b.primarySolidPhase, b.phaseNameNotes)}`);
  const notes = Object.entries(b.phaseNameNotes ?? {});
  if (notes.length) lines.push(`${notes.map(([name]) => name).join(", ")}: ${notes[0][1]}.`);
  if (typeof b.stepC === "number") {
    const balance = typeof b.massBalanceMaxAbsError === "number"
      ? `; mass balance error ${b.massBalanceMaxAbsError.toExponential(1)}` : "";
    lines.push(`Step ${b.stepC} °C, ${b.steps ?? "n/a"} equilibrium steps${balance}.`);
  }
  return lines;
}

/** Temperature window (degC) and grid step of a pycalphad request, chosen from the base element (largest
 * amount) so the melting range lies inside the grid: Al and Mg alloys melt below 700 degC, Ti alloys near
 * 1600-1700 degC. A liquidus outside the window is reported as unavailable by the engine, never guessed. */
export function calphadTemperatureWindow(elements: Record<string, number>): { tMin: number; tMax: number; tStep: number } {
  let base = "";
  let best = -Infinity;
  for (const [el, val] of Object.entries(elements)) {
    if (typeof val === "number" && val > best) {
      best = val;
      base = el;
    }
  }
  switch (base.trim().toLowerCase()) {
    case "al":
      return { tMin: 400, tMax: 750, tStep: 10 };
    case "mg":
      return { tMin: 350, tMax: 700, tStep: 10 };
    case "ti":
      return { tMin: 600, tMax: 1750, tStep: 25 };
    default:
      return { tMin: 500, tMax: 1550, tStep: 25 };
  }
}

/** A phase name with "(ordering not checked)" when the engine flagged it as an order/disorder model phase. */
export function withOrderingNote(name: string, ...noteMaps: (Record<string, string> | undefined | null)[]): string {
  return noteMaps.some((m) => m && m[name]) ? `${name} (ordering not checked)` : name;
}

/** The probe temperature kept on the solved grid: clamped into [tMin, tMax] and snapped to the step. */
export function clampProbeToRange(t: number, tMin: number, tMax: number, step: number): number {
  if (!Number.isFinite(t) || !(tMax >= tMin)) return tMin;
  const clamped = Math.min(tMax, Math.max(tMin, t));
  if (!(step > 0)) return clamped;
  return Math.min(tMax, tMin + Math.round((clamped - tMin) / step) * step);
}

// ---- request identity (storm control) ----

/** Composition as a stable string: symbols sorted, so key order and object identity do not matter. */
export function compositionKey(elements: Record<string, number>): string {
  return JSON.stringify(Object.entries(elements).sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0)));
}

/** Identity of the shared specimen: name plus sorted composition (not its lastModified stamp). */
export function specimenKey(name: string, elements: Record<string, number>): string {
  return JSON.stringify([name, compositionKey(elements)]);
}

/** Identity of one CALPHAD request. Equal keys mean an identical request body, so it is never sent twice. */
export function calphadRequestKey(
  elements: Record<string, number>,
  unit: string,
  window: { tMin: number; tMax: number; tStep: number },
  usePython: boolean,
  databaseId: string,
  refinement: boolean,
  tolerance: number,
  scheil: boolean,
): string {
  return JSON.stringify([compositionKey(elements), unit, window.tMin, window.tMax, window.tStep, usePython, databaseId, refinement, tolerance, scheil]);
}

/** A chemical potential in kJ/mol as text, or "Unavailable" when missing or not finite (never 0). */
export function formatChemicalPotentialKJ(muJ_per_mol: number | null | undefined): string {
  return typeof muJ_per_mol === "number" && Number.isFinite(muJ_per_mol)
    ? `${(muJ_per_mol / 1000).toFixed(2)} kJ/mol` : "Unavailable";
}
