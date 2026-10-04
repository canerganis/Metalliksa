// Display text for Tafel / corrosion-rate values that can be unavailable.
// python/tafel_corrosion_rate_solver.py (and the client Tafel engine in tafelParser.ts) report a value as null when it
// was not supplied or could not be fitted; it is shown as "Unavailable" with the engine's reason, never as an invented
// number (no assumed slope, R2 or corrosion current).
import type { TafelFitResult } from "../types/tafel";
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

/** Mils per millimetre: 1 mil = 0.001 in = 0.0254 mm exactly (the Python engines use the same factor). */
export const MILS_PER_MM = 1000 / 25.4;

/**
 * What a chart may draw of the Evans intersection. E_corr / log(i_corr) are null when the intersection is
 * unavailable; the scales then anchor on the measured current valley (a measured value) and the intersection markers,
 * zone shading and callout must not be drawn (`intersectionKnown` false).
 */
export function tafelIntersectionAnchors(
  fit: Pick<TafelFitResult, "eCorr" | "logIcorr" | "rawEcorrValley" | "rawIcorrValley">
): { intersectionKnown: boolean; eCorrRef: number; logIcorrRef: number } {
  return {
    intersectionKnown: fit.eCorr !== null && fit.logIcorr !== null,
    eCorrRef: fit.eCorr ?? fit.rawEcorrValley,
    logIcorrRef: fit.logIcorr ?? Math.log10(Math.max(1e-9, fit.rawIcorrValley)),
  };
}

export type DigitalTwinPassivation =
  | "Immune"
  | "Passive Stable"
  | "Susceptible to Pitting"
  | "Active Dissolution"
  | "Unresolved";

/**
 * The `electrochemistry` payload the Tafel lab syncs to the Digital Twin. An unavailable value is sent as null and an
 * unavailable severity as "Unresolved" (never as the severity of a corrosion rate that does not exist).
 */
export function digitalTwinElectrochemistry(fit: TafelFitResult): {
  corrosionRateMpy: number | null;
  openCircuitPotentialEcorrV: number | null;
  polarizationResistanceRpOhmCm2: number | null;
  pittingPotentialEpitV: number | undefined;
  eisImpedanceModuleOhm: number | null;
  passivationQuality: DigitalTwinPassivation;
} {
  let passivationQuality: DigitalTwinPassivation;
  if (fit.severity === null) passivationQuality = "Unresolved";
  else if (fit.severity === "Immune / Highly Resistant") passivationQuality = "Immune";
  else if (fit.severity === "Passivated / Good") passivationQuality = "Passive Stable";
  else if (fit.severity === "Moderate (Caution)") passivationQuality = "Susceptible to Pitting";
  else passivationQuality = "Active Dissolution";
  return {
    corrosionRateMpy: fit.corrosionRateMpy,
    openCircuitPotentialEcorrV: fit.eCorr,
    polarizationResistanceRpOhmCm2: fit.rp_ohm_cm2,
    pittingPotentialEpitV: fit.pittingPotentialEpit_V || undefined,
    eisImpedanceModuleOhm: fit.rp_ohm_cm2,
    passivationQuality,
  };
}
