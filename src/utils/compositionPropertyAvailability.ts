/**
 * Composition-to-property availability for the shared specimen records (Alloy Builder and the shared LPBF specimen).
 *
 * The stores used to fill liquidus/solidus/solvus, yield strength, UTS, Young's modulus and elongation with invented
 * linear formulas per base metal (e.g. Ni yield = 320 + 85 x gamma-prime formers; any steel >= 750 MPa). None of
 * those formulas had a source or a validity range, so the fields are now null and every consumer shows this reason
 * instead of a number. A value only comes back when a real model or a cited/measured record supplies it.
 */
export const COMPOSITION_PROPERTY_UNAVAILABLE_NOTE =
  "Unavailable: no validated composition-to-property model is implemented. Liquidus/solidus/solvus, yield strength, " +
  "UTS, Young's modulus and elongation are not computed from composition here.";

/** Fields of a specimen record that no longer carry composition-heuristic numbers. */
export const COMPOSITION_HEURISTIC_PROPERTY_FIELDS = [
  "liquidus_C",
  "solidus_C",
  "freezingRange_C",
  "solvus_C",
  "yieldStrength_25C_MPa",
  "uts_25C_MPa",
  "youngsModulus_GPa",
  "elongation_pct",
] as const;

export type CompositionHeuristicPropertyField = (typeof COMPOSITION_HEURISTIC_PROPERTY_FIELDS)[number];

/** Null every heuristic property field of a persisted specimen-like object (non-objects pass through). */
export function withoutCompositionHeuristicProperties<T>(specimen: T): T {
  if (!specimen || typeof specimen !== "object" || Array.isArray(specimen)) return specimen;
  const next: Record<string, unknown> = { ...(specimen as Record<string, unknown>) };
  for (const field of COMPOSITION_HEURISTIC_PROPERTY_FIELDS) next[field] = null;
  return next as T;
}

/** A finite positive number, or null. Older records (and the removed heuristics) may still hand in other values. */
export function availableProperty(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) && value > 0 ? value : null;
}

/**
 * Strengths a converter may load from a specimen record: only real (finite, positive) values. Composition-only records
 * carry null (unavailable), and then nothing is loaded rather than a placeholder.
 */
export function specimenStrengthsToLoad(
  specimen: { yieldStrength_25C_MPa?: unknown; uts_25C_MPa?: unknown } | null | undefined
): { yieldMpa: number | null; utsMpa: number | null } {
  return {
    yieldMpa: availableProperty(specimen?.yieldStrength_25C_MPa),
    utsMpa: availableProperty(specimen?.uts_25C_MPa),
  };
}

/** Elemental densities (g/cm3, room temperature, CRC Handbook of Chemistry and Physics values). */
export const ELEMENTAL_DENSITY_GCM3: Readonly<Record<string, number>> = {
  Ni: 8.908,
  Fe: 7.874,
  Cr: 7.19,
  Co: 8.9,
  Mo: 10.28,
  W: 19.25,
  Ta: 16.69,
  Al: 2.7,
  Ti: 4.506,
  Nb: 8.57,
  C: 2.26,
  B: 2.34,
  Zr: 6.52,
  Hf: 13.31,
  V: 6.11,
  Mn: 7.21,
  Si: 2.33,
  Cu: 8.96,
  Mg: 1.738,
  Zn: 7.14,
  Re: 21.02,
  Sc: 2.985,
};

export type RuleOfMixturesDensity =
  | { status: "computed"; density_gcm3: number; note: string }
  | { status: "unavailable"; density_gcm3: null; note: string };

const DENSITY_SCOPE_NOTE =
  "Inverse rule of mixtures over wt.% with tabulated elemental densities (ideal mixing; ignores excess volume, " +
  "phases and porosity). Not a measured density.";

/**
 * rho = sum(w_i) / sum(w_i / rho_i) over the weight-percent composition. Unavailable (no silent 8.0 g/cm3 fallback)
 * when the composition is in at.%, empty, or contains an element without a tabulated density.
 */
export function ruleOfMixturesDensity(
  composition: Record<string, number> | undefined,
  unit: "wt_pct" | "at_pct" | string = "wt_pct"
): RuleOfMixturesDensity {
  if (unit !== "wt_pct") {
    return { status: "unavailable", density_gcm3: null, note: "Unavailable: the composition is in at.%; the rule of mixtures here needs wt.%." };
  }
  const entries = Object.entries(composition ?? {}).filter(([, pct]) => typeof pct === "number" && Number.isFinite(pct) && pct > 0);
  if (entries.length === 0) {
    return { status: "unavailable", density_gcm3: null, note: "Unavailable: the composition has no positive element content." };
  }
  const missing = entries.filter(([element]) => !(element in ELEMENTAL_DENSITY_GCM3)).map(([element]) => element);
  if (missing.length > 0) {
    return {
      status: "unavailable",
      density_gcm3: null,
      note: `Unavailable: no tabulated elemental density for ${missing.join(", ")}.`,
    };
  }
  let mass = 0;
  let volume = 0;
  for (const [element, pct] of entries) {
    mass += pct;
    volume += pct / ELEMENTAL_DENSITY_GCM3[element];
  }
  return { status: "computed", density_gcm3: parseFloat((mass / volume).toFixed(3)), note: DENSITY_SCOPE_NOTE };
}
