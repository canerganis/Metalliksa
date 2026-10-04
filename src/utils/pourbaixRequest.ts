import type { ExperimentalEpHEntry } from "../types/pourbaix";

export interface PourbaixRequestInputs {
  primaryElement: string;
  temperature_C: number;
  ionActivity: number;
  chlorideActivity: number;
  experimentalPoints: ExperimentalEpHEntry[];
}

/** Only the user-supplied point fields go into the request; solver-derived diagnostics (potential_V_SHE, regime, ...) are never echoed back to the solver. */
export function pourbaixPointBody(p: ExperimentalEpHEntry) {
  const body: Partial<ExperimentalEpHEntry> = { id: p.id, name: p.name, pH: p.pH, potential_V: p.potential_V, refElectrode: p.refElectrode };
  if (p.currentDensity_uA_cm2 !== undefined) body.currentDensity_uA_cm2 = p.currentDensity_uA_cm2;
  if (p.timeHours !== undefined) body.timeHours = p.timeHours;
  if (p.stageName !== undefined) body.stageName = p.stageName;
  if (p.notes !== undefined) body.notes = p.notes;
  return body;
}

/** Body sent to the Python Pourbaix solver (unchanged from the inline original). */
export function buildPourbaixRequest(inputs: PourbaixRequestInputs) {
  return {
    element: inputs.primaryElement,
    temperature_C: inputs.temperature_C,
    ionActivity_log10: Math.log10(inputs.ionActivity),
    chloride_ppm: Math.round(inputs.chlorideActivity * 35453), // Convert Molar to ppm Cl-
    experimentalPoints: inputs.experimentalPoints.length > 0 ? inputs.experimentalPoints.map(pourbaixPointBody) : undefined,
  };
}

/** User-supplied point fields; solver-derived diagnostics are excluded so enrichment cannot retrigger a solve. */
export function pourbaixPointInput(p: ExperimentalEpHEntry) {
  return [p.id, p.name, p.pH, p.potential_V, p.refElectrode, p.currentDensity_uA_cm2 ?? null, p.timeHours ?? null, p.stageName ?? null, p.notes ?? null];
}

export function pourbaixRequestSignature(inputs: PourbaixRequestInputs): string {
  const { experimentalPoints, ...rest } = buildPourbaixRequest(inputs);
  return JSON.stringify([rest, (experimentalPoints ?? []).map(pourbaixPointInput)]);
}
