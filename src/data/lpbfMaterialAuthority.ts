/**
 * Read-only view of the Python LPBF material authority for the UI.
 *
 * Every alloy number here comes from src/generated/lpbfMaterialAuthority.json, which
 * scripts/emit-lpbf-material-authority.py generates from python/four_alloy_materials.py
 * (IN625: python/lpbf_thermal_solver.py SECONDARY_THERMOPHYSICAL_DB). Do not add alloy
 * numbers to this file or to its consumers; change the Python authority and regenerate.
 * Equality is tested in tests/lpbf-material-authority.test.ts and
 * python/test_lpbf_material_authority_json.py. Unknown alloys throw: no surrogate alloy.
 * Labels are the authority's own: the four alloys carry quality "estimated" (provenance not
 * independently verified). The IN625 row is NOT from the four-alloy authority: it carries
 * quality "secondary-unreconciled", the registry catalog label ("missing") and the list of
 * other IN625 values Python holds; use authorityThermalProvenance() to show that label.
 * This module adds no evidence claim.
 */
import authorityDocument from "../generated/lpbfMaterialAuthority.json";

export type AuthorityAlloyId = "ti6al4v" | "ss316l" | "alsi10mg" | "in718";
/** Alloys with a Python constant-property row: the four locked alloys plus the IN625 secondary row. */
export type AuthorityThermalAlloyId = AuthorityAlloyId | "in625";

export interface AuthorityThermal {
  readonly base: string;
  readonly liquidus_C: number;
  readonly solidus_C: number;
  readonly boiling_C: number;
  readonly M_molar_kg_mol: number;
  readonly density_kg_m3: number;
  readonly density_liquid_kg_m3: number;
  readonly thermal_conductivity_W_mK: number;
  readonly thermal_conductivity_liquid_W_mK: number;
  readonly specific_heat_J_kgK: number;
  readonly specific_heat_liquid_J_kgK: number;
  readonly latent_heat_fusion_J_kg: number;
  readonly latent_heat_vap_J_kg: number;
  readonly absorptivity_IR: number;
  readonly absorptivity_Green: number;
  readonly surface_tension_N_m: number;
  readonly d_gamma_dT_N_mK: number;
  readonly viscosity_Pa_s: number;
  readonly thermal_expansion_1_K: number;
  readonly youngs_modulus_GPa: number;
  readonly poissons_ratio: number;
  readonly pdas_A1: number;
  readonly sdas_B1: number;
}

export interface AuthorityPvWindow {
  readonly powerMin_W: number;
  readonly powerMax_W: number;
  readonly speedMin_mm_s: number;
  readonly speedMax_mm_s: number;
}

export interface AuthorityAlloyEntry {
  readonly thermalName: string;
  readonly slicerName: string;
  readonly quality: string;
  readonly source: string;
  readonly canonicalSourceSha256: string;
  readonly thermal: AuthorityThermal;
  readonly literaturePvWindow: AuthorityPvWindow;
}

export interface AuthorityUnreconciledValue {
  readonly quantity: string;
  readonly unit: string;
  readonly values: readonly { readonly module: string; readonly use: string; readonly value: number }[];
}

export interface AuthoritySecondaryEntry {
  readonly thermalName: string;
  readonly quality: string;
  readonly source: string;
  readonly registryCatalogQuality: string;
  readonly registryCatalogNote: string;
  readonly note: string;
  readonly unreconciledPythonValues: readonly AuthorityUnreconciledValue[];
  readonly thermal: AuthorityThermal;
}

export interface LpbfMaterialAuthorityDocument {
  readonly schemaVersion: number;
  readonly authority: string;
  readonly authoritySchemaVersion: number;
  readonly alloyIds: readonly AuthorityAlloyId[];
  readonly alloys: Readonly<Record<AuthorityAlloyId, AuthorityAlloyEntry>>;
  readonly secondary: Readonly<{ in625: AuthoritySecondaryEntry }>;
}

/** The document shape this accessor was written for; a regenerated file with another version must fail loudly. */
export const LPBF_MATERIAL_AUTHORITY_SCHEMA_VERSION = 1;

export function checkedAuthorityDocument(document: unknown): LpbfMaterialAuthorityDocument {
  const version = (document as { schemaVersion?: unknown } | null)?.schemaVersion;
  if (version !== LPBF_MATERIAL_AUTHORITY_SCHEMA_VERSION) {
    throw new Error(`lpbfMaterialAuthority.json schemaVersion ${String(version)} is not the supported ${LPBF_MATERIAL_AUTHORITY_SCHEMA_VERSION}; regenerate it and update this accessor.`);
  }
  return document as LpbfMaterialAuthorityDocument;
}

export const LPBF_MATERIAL_AUTHORITY = checkedAuthorityDocument(authorityDocument);

function unknownAlloy(alloyId: string, scope: string): never {
  throw new Error(`No ${scope} in the Python material authority for alloy "${alloyId}"; no surrogate alloy is substituted.`);
}

export function isAuthorityAlloyId(alloyId: string): alloyId is AuthorityAlloyId {
  return (LPBF_MATERIAL_AUTHORITY.alloyIds as readonly string[]).includes(alloyId);
}

export function authorityAlloy(alloyId: string): AuthorityAlloyEntry {
  if (!isAuthorityAlloyId(alloyId)) unknownAlloy(alloyId, "alloy entry");
  return LPBF_MATERIAL_AUTHORITY.alloys[alloyId];
}

/** Constant thermophysical row: four-alloy authority, or the labelled IN625 secondary row. */
export function authorityThermal(alloyId: string): AuthorityThermal {
  if (isAuthorityAlloyId(alloyId)) return LPBF_MATERIAL_AUTHORITY.alloys[alloyId].thermal;
  if (alloyId === "in625") return LPBF_MATERIAL_AUTHORITY.secondary.in625.thermal;
  return unknownAlloy(alloyId, "thermophysical row");
}

/** The label and source that belong next to an authorityThermal() row. */
export function authorityThermalProvenance(alloyId: string): { readonly quality: string; readonly source: string } {
  if (isAuthorityAlloyId(alloyId)) {
    const entry = LPBF_MATERIAL_AUTHORITY.alloys[alloyId];
    return { quality: entry.quality, source: entry.source };
  }
  if (alloyId === "in625") {
    const entry = LPBF_MATERIAL_AUTHORITY.secondary.in625;
    return { quality: entry.quality, source: entry.source };
  }
  return unknownAlloy(alloyId, "thermophysical row");
}

export function authorityPvWindow(alloyId: string): AuthorityPvWindow {
  return authorityAlloy(alloyId).literaturePvWindow;
}

/** Unit conversion only (°C -> K), rounded to 0.01 K so float noise does not reach the display. */
export function celsiusToKelvin(celsius: number): number {
  return Number((celsius + 273.15).toFixed(2));
}

/** Inputs for the Phase 22 transient 3D GPU RPC (solid/liquid rows of the authority). */
export interface TransientGpuMaterialInputs {
  readonly rho: number;
  readonly L_f: number;
  readonly T_solidus: number;
  readonly T_liquidus: number;
  readonly cp_solid: number;
  readonly cp_liquid: number;
  readonly k_solid: number;
  readonly k_liquid: number;
}

export function transientGpuMaterialInputs(alloyId: AuthorityAlloyId): TransientGpuMaterialInputs {
  const t = authorityAlloy(alloyId).thermal;
  return {
    rho: t.density_kg_m3,
    L_f: t.latent_heat_fusion_J_kg,
    T_solidus: celsiusToKelvin(t.solidus_C),
    T_liquidus: celsiusToKelvin(t.liquidus_C),
    cp_solid: t.specific_heat_J_kgK,
    cp_liquid: t.specific_heat_liquid_J_kgK,
    k_solid: t.thermal_conductivity_W_mK,
    k_liquid: t.thermal_conductivity_liquid_W_mK,
  };
}

/** Inputs for the solidification-microstructure screening RPC (solid k, liquidus, IR absorptivity). */
export interface SolidificationMaterialInputs {
  readonly k_WmK: number;
  readonly liquidus_K: number;
  readonly absorptivity: number;
}

export function solidificationMaterialInputs(alloyId: AuthorityAlloyId): SolidificationMaterialInputs {
  const t = authorityAlloy(alloyId).thermal;
  return {
    k_WmK: t.thermal_conductivity_W_mK,
    liquidus_K: celsiusToKelvin(t.liquidus_C),
    absorptivity: t.absorptivity_IR,
  };
}
