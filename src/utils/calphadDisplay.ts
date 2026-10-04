/**
 * Display rules for the CALPHAD Studio (fx-calphad lane).
 *
 * The Python engine returns status "unavailable" (success false) instead of a
 * non-thermodynamic fallback, and it sets a critical temperature to null when the grid
 * cannot support it (solidus at the grid bound, gamma-prime known by phase name only).
 * Nothing here invents a number: a null renders as "Unavailable" with its reason.
 */

export interface CalphadFieldStatus {
  status?: string;
  reason?: string;
  note?: string;
}

/** The Python "unavailable" envelope fields the UI shows. */
export interface CalphadUnavailable {
  unavailableKind: string;
  reason: string;
  reasons: string[];
  missingElements?: string[];
  databaseUsed?: string;
  databaseStatus?: string;
}

export function parseCalphadUnavailable(data: any): CalphadUnavailable | null {
  if (!data || typeof data !== "object" || data.status !== "unavailable") return null;
  const reason = typeof data.reason === "string" && data.reason ? data.reason : "CALPHAD engine unavailable";
  return {
    unavailableKind: typeof data.unavailableKind === "string" ? data.unavailableKind : "unavailable",
    reason,
    reasons: Array.isArray(data.reasons) ? data.reasons.filter((r: unknown) => typeof r === "string") : [reason],
    missingElements: Array.isArray(data.missingElements) ? data.missingElements.map(String) : undefined,
    databaseUsed: typeof data.databaseUsed === "string" ? data.databaseUsed : undefined,
    databaseStatus: typeof data.databaseStatus === "string" ? data.databaseStatus : undefined,
  };
}

export function formatCalphadUnavailable(u: CalphadUnavailable): string {
  return `Python CALPHAD (pycalphad) unavailable: ${u.reason}.`;
}

/** Text of one critical-temperature card: a number with unit, or "Unavailable" + the reason as tooltip. */
export function formatCriticalTemperature(
  value: number | null | undefined,
  status?: CalphadFieldStatus,
): { text: string; title: string; available: boolean } {
  if (typeof value === "number" && Number.isFinite(value)) {
    return { text: `${value}°C`, title: status?.note ?? "", available: true };
  }
  return { text: "Unavailable", title: status?.reason ?? "Not available for this calculation.", available: false };
}

export function formatFreezingRange(value: number | null | undefined): string {
  return typeof value === "number" && Number.isFinite(value) ? `${value} K` : "Unavailable";
}

export interface CalphadProvenanceInput {
  isPythonEngine?: boolean;
  isEmpirical?: boolean;
  thermodynamicModel?: string;
  databaseUsed?: string;
}

export const CLIENT_MODEL_LABEL = "Client-side simplified screening model (not CALPHAD, not pycalphad)";
export const CLIENT_DATABASE_LABEL = "Built-in client TDB model (not an assessment)";

/** Labels for the model/database lines; a client screening result is never labelled as pycalphad. */
export function calphadProvenanceLabels(result: CalphadProvenanceInput): {
  model: string;
  database: string;
  isPycalphad: boolean;
} {
  const isPycalphad = result.isPythonEngine === true && result.isEmpirical !== true;
  if (isPycalphad) {
    return {
      model: result.thermodynamicModel || "pycalphad CEF Gibbs minimisation",
      database: result.databaseUsed || "Unnamed database",
      isPycalphad: true,
    };
  }
  return { model: CLIENT_MODEL_LABEL, database: CLIENT_DATABASE_LABEL, isPycalphad: false };
}

export const SOLUTE_DEFAULT_K_SOURCE = "default-table-not-thermodynamic";

export function partitionSourceNote(source: string | undefined): string | null {
  return source === SOLUTE_DEFAULT_K_SOURCE ? "default screening value, not CALPHAD" : null;
}
