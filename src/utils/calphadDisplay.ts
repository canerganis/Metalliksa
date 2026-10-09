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
  /** A deviation of the database from reported values for this field (shown next to the number). */
  knownDeviation?: string;
}

/** The Python "unavailable" envelope fields the UI shows. */
export interface CalphadUnavailable {
  unavailableKind: string;
  reason: string;
  reasons: string[];
  missingElements?: string[];
  baseElement?: string;
  assessedBaseElements?: string[];
  /** Scope text of the database that was asked for or came closest. */
  databaseSuitability?: string;
  databaseUsed?: string;
  databaseStatus?: string;
  /** pycalphad grid points that returned non-finite results (unavailableKind pycalphad-equilibrium-failed). */
  nonConvergedPoints?: number;
  gridPoints?: number;
}

export function parseCalphadUnavailable(data: any): CalphadUnavailable | null {
  if (!data || typeof data !== "object" || data.status !== "unavailable") return null;
  const reason = typeof data.reason === "string" && data.reason ? data.reason : "CALPHAD engine unavailable";
  return {
    unavailableKind: typeof data.unavailableKind === "string" ? data.unavailableKind : "unavailable",
    reason,
    reasons: Array.isArray(data.reasons) ? data.reasons.filter((r: unknown) => typeof r === "string") : [reason],
    missingElements: Array.isArray(data.missingElements) ? data.missingElements.map(String) : undefined,
    baseElement: typeof data.baseElement === "string" ? data.baseElement : undefined,
    assessedBaseElements: Array.isArray(data.assessedBaseElements) ? data.assessedBaseElements.map(String) : undefined,
    databaseSuitability: typeof data.databaseSuitability === "string" ? data.databaseSuitability : undefined,
    nonConvergedPoints: typeof data.nonConvergedPoints === "number" ? data.nonConvergedPoints : undefined,
    gridPoints: typeof data.gridPoints === "number" ? data.gridPoints : undefined,
    databaseUsed: typeof data.databaseUsed === "string" ? data.databaseUsed : undefined,
    databaseStatus: typeof data.databaseStatus === "string" ? data.databaseStatus : undefined,
  };
}

export function formatCalphadUnavailable(u: CalphadUnavailable): string {
  return `Python CALPHAD (pycalphad) unavailable: ${u.reason}.`;
}

/** Extra lines under the unavailable banner (scope, missing elements, convergence). */
export function calphadUnavailableDetails(u: CalphadUnavailable): string[] {
  const lines: string[] = [];
  if (u.missingElements && u.missingElements.length > 0) {
    lines.push(`Elements missing from the database: ${u.missingElements.join(", ")}.`);
  }
  if (u.databaseSuitability) {
    lines.push(`Database scope${u.databaseUsed ? ` (${u.databaseUsed})` : ""}: ${u.databaseSuitability}`);
  }
  if (typeof u.nonConvergedPoints === "number" && typeof u.gridPoints === "number") {
    lines.push(`${u.nonConvergedPoints} of ${u.gridPoints} grid points did not converge.`);
  }
  return lines;
}

/** G or another nullable energy: a non-converged point has no value. */
export function formatNullable(value: number | null | undefined, unit: string): string {
  return typeof value === "number" && Number.isFinite(value) ? `${value} ${unit}` : "n/a (not converged)";
}

/** "n/a" instead of an invented time when the engine did not report one. */
export function formatComputeTime(ms: number | null | undefined): string {
  return typeof ms === "number" && Number.isFinite(ms) ? `${ms} ms` : "n/a";
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
  databaseSuitability?: string;
  /** Short scope flag of a scoped database (what it may and may not be used for); absent for other databases. */
  databaseScopeFlag?: string;
}

export const CLIENT_MODEL_LABEL = "Client-side simplified screening model (not CALPHAD, not pycalphad)";
export const CLIENT_DATABASE_LABEL = "Built-in client TDB model (not an assessment)";

/** Labels for the model/database lines; a client screening result is never labelled as pycalphad. */
export function calphadProvenanceLabels(result: CalphadProvenanceInput): {
  model: string;
  database: string;
  /** Scope of the database (which base elements it is assessed for); null for a client result. */
  scope: string | null;
  /** Scope flag of a scoped database (for example mc_ti); null when the database carries none. */
  scopeFlag: string | null;
  isPycalphad: boolean;
} {
  const isPycalphad = result.isPythonEngine === true && result.isEmpirical !== true;
  if (isPycalphad) {
    return {
      model: result.thermodynamicModel || "pycalphad CEF Gibbs minimisation",
      database: result.databaseUsed || "Unnamed database",
      scope: result.databaseSuitability || null,
      scopeFlag: result.databaseScopeFlag || null,
      isPycalphad: true,
    };
  }
  return { model: CLIENT_MODEL_LABEL, database: CLIENT_DATABASE_LABEL, scope: null, scopeFlag: null, isPycalphad: false };
}

export const SOLUTE_DEFAULT_K_SOURCE = "default-table-not-thermodynamic";

export function partitionSourceNote(source: string | undefined): string | null {
  return source === SOLUTE_DEFAULT_K_SOURCE ? "default screening value, not CALPHAD" : null;
}
