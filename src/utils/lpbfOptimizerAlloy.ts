import { mapDisplayNameToAlloyId } from "./lpbfFourAlloySchema";

// Alloys python/four_alloy_materials.py can resolve for the optimizer (IN625 has no solver material there).
const OPTIMIZER_ALLOYS = ["ti6al4v", "ss316l", "alsi10mg", "in718"] as const;
export type OptimizerAlloyKey = (typeof OPTIMIZER_ALLOYS)[number];

export const OPTIMIZER_MAX_ITERATIONS = 30;
export const OPTIMIZER_DEFAULT_BEAM_DIAMETER_UM = 80;
export const OPTIMIZER_DEFAULT_PREHEAT_C = 80;

// Plain shape (not a discriminated union): the project tsconfig is not strict, so boolean discriminants do not narrow.
export interface OptimizerAlloyResolution {
  ok: boolean;
  alloyKey: OptimizerAlloyKey | null;
  reason: string | null;
}

/** Derives the solver alloy key from the specimen display name (the specimen id is not an alloy key). */
export function resolveOptimizerAlloy(specimenName: string | null | undefined): OptimizerAlloyResolution {
  const id = specimenName ? mapDisplayNameToAlloyId(specimenName) : null;
  if (id && (OPTIMIZER_ALLOYS as readonly string[]).includes(id)) {
    return { ok: true, alloyKey: id as OptimizerAlloyKey, reason: null };
  }
  return {
    ok: false,
    alloyKey: null,
    reason: id
      ? `Alloy "${id}" has no solver material in the optimizer backend.`
      : `Active material "${specimenName ?? "(none)"}" does not map to a supported LPBF alloy (Ti-6Al-4V, 316L, AlSi10Mg, IN718).`,
  };
}
