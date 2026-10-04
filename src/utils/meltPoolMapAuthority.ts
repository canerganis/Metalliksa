/**
 * Liquidus / solidus used by the thermal-map illustration, read from the Python material authority
 * (src/data/lpbfMaterialAuthority.ts, generated from python/four_alloy_materials.py). No fixed
 * temperatures and no surrogate alloy: an alloy the authority does not hold returns null and the
 * caller must not draw the interpolated map.
 */
import { LPBF_MATERIAL_AUTHORITY, authorityThermal, type AuthorityAlloyId } from "../data/lpbfMaterialAuthority";

export interface MapPhaseTemperatures {
  readonly alloyId: AuthorityAlloyId | "in625";
  readonly liquidus_C: number;
  readonly solidus_C: number;
  /** The authority's own quality label for the row ("estimated", "secondary-unreconciled"). */
  readonly quality: string;
}

function normalise(name: string): string {
  return name.trim().toLowerCase();
}

/** Match a solver material name (e.g. "Inconel 718", "316L Stainless Steel") or an authority id. */
export function mapPhaseTemperaturesC(materialName: string): MapPhaseTemperatures | null {
  const wanted = normalise(materialName);
  for (const alloyId of LPBF_MATERIAL_AUTHORITY.alloyIds) {
    const entry = LPBF_MATERIAL_AUTHORITY.alloys[alloyId];
    if (wanted === alloyId || wanted === normalise(entry.thermalName)) {
      const thermal = authorityThermal(alloyId);
      return { alloyId, liquidus_C: thermal.liquidus_C, solidus_C: thermal.solidus_C, quality: entry.quality };
    }
  }
  const in625 = LPBF_MATERIAL_AUTHORITY.secondary.in625;
  if (wanted === "in625" || wanted === normalise(in625.thermalName)) {
    const thermal = authorityThermal("in625");
    return { alloyId: "in625", liquidus_C: thermal.liquidus_C, solidus_C: thermal.solidus_C, quality: in625.quality };
  }
  return null;
}
