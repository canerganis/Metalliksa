/**
 * Display helpers for the continuum-elasticity result (python/dft_property_calculator.py, v4.1).
 * The engine returns null (with a reason) instead of a number when it would have to invent one; these
 * helpers render that as "Unavailable" and never as 0, NaN or a default.
 */
import type { PythonDFTResult } from "../services/pythonComputationService";

export const UNAVAILABLE_TEXT = "Unavailable";

/** "123.4 K" for a finite number, "Unavailable" for null / undefined / NaN / Infinity. */
export function formatOrUnavailable(value: number | null | undefined, unit: string): string {
  return typeof value === "number" && Number.isFinite(value) ? `${value} ${unit}` : UNAVAILABLE_TEXT;
}

export function formatZener(value: number | null | undefined): string {
  return typeof value === "number" && Number.isFinite(value) ? String(value) : "n/a (cubic crystals only)";
}

type DirectionalModuli = NonNullable<PythonDFTResult["directionalYoungsModuli"]>;

/** Visible direction text: the engine's label (lattice [hkl] only where exact, otherwise "(h,k,l) Cartesian"). */
export function directionLabel(direction: DirectionalModuli[number]): string {
  return direction.label ?? direction.direction;
}

/**
 * Measured compute time of the engine, or null when none was reported (an unreachable engine has no time;
 * 0 ms is never invented).
 */
export function computeTimeText(outcome: { computeTimeMs?: number | null } | null | undefined): string | null {
  const ms = outcome?.computeTimeMs;
  return typeof ms === "number" && Number.isFinite(ms) ? `${ms} ms` : null;
}

/**
 * One line saying what the numbers are: the engine's label plus where the constants came from. The reference
 * status is appended only when sourceNotes (library entries) does not already state it.
 */
export function provenanceLine(result: Pick<PythonDFTResult, "label" | "sourceNotes" | "referenceStatus">): string {
  const statusText = result.referenceStatus ? `reference status: ${result.referenceStatus}` : undefined;
  const parts = [
    result.label ?? "Continuum elasticity (not a DFT calculation)",
    result.sourceNotes,
    statusText && !(result.sourceNotes ?? "").includes(statusText) ? statusText : undefined,
  ];
  return parts.filter((part): part is string => typeof part === "string" && part.length > 0).join(" | ");
}
