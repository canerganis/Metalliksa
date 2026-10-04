// Display text for Tafel / corrosion-rate values that can be unavailable.
// python/tafel_corrosion_rate_solver.py (and the client Tafel engine in tafelParser.ts) report a value as null when it
// was not supplied or could not be fitted; it is shown as "Unavailable" with the engine's reason, never as an invented
// number (no assumed slope, R2 or corrosion current).
import { UNAVAILABLE_TEXT } from "./hardnessConversion";

export { UNAVAILABLE_TEXT };

const finite = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);

export interface TafelNumberFormat {
  /** toFixed digits; omitted: the number as stored. */
  digits?: number;
  /** Thousands separators (en-US), as the Rp displays used. */
  grouped?: boolean;
  /** Placeholder for a missing value; default "Unavailable". */
  fallback?: string;
}

/** "1.25" or "Unavailable" (bare value). */
export function fmtTafelNumber(value: number | null | undefined, format: TafelNumberFormat = {}): string {
  if (!finite(value)) return format.fallback ?? UNAVAILABLE_TEXT;
  if (format.grouped) {
    return value.toLocaleString("en-US", format.digits === undefined ? undefined : { maximumFractionDigits: format.digits });
  }
  return format.digits === undefined ? String(value) : value.toFixed(format.digits);
}

/** "1.25 µA/cm²" or "Unavailable" (value and unit; the unit is dropped with the value). */
export function fmtTafelQuantity(value: number | null | undefined, unit: string, format: TafelNumberFormat = {}): string {
  return finite(value) ? `${fmtTafelNumber(value, format)} ${unit}` : (format.fallback ?? UNAVAILABLE_TEXT);
}

/** "R² = 0.9981" or "R²: Unavailable". */
export function fmtTafelR2(r2: number | null | undefined): string {
  return finite(r2) ? `R² = ${r2}` : `R²: ${UNAVAILABLE_TEXT}`;
}

export interface TafelUnavailableInfo {
  unavailableReason?: string | null;
  unavailable?: Readonly<Record<string, string | undefined>> | null;
}

/** The engine's reason for an unavailable value, "" when there is none (nothing is unavailable). */
export function tafelUnavailableReason(info: TafelUnavailableInfo | null | undefined): string {
  if (!info) return "";
  if (info.unavailableReason) return info.unavailableReason;
  const reasons = Object.values(info.unavailable ?? {}).filter((r): r is string => typeof r === "string" && r !== "");
  return reasons.join("; ");
}
