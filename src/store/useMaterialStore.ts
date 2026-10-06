import { create } from "zustand";
import { persist } from "zustand/middleware";
import { setActivePipelineMaterial, PipelineMaterialPayload } from "../utils/materialDataPipeline";
import { estimateSpecimenHardnessHV, type HardnessHVEstimateStatus } from "../utils/hardnessStrengthEstimate";
import { deriveSpecimenProperties } from "./useMaterialSpecimenStore";
import { materialCategoryForBase } from "../utils/materialCategory";
import { ELEMENTAL_DENSITY_GCM3, withoutCompositionHeuristicProperties } from "../utils/compositionPropertyAvailability";

export type BaseMetalType = "Ni" | "Fe" | "Ti" | "Al" | "Cu" | "Co" | "Mg" | "Refractory" | "Other";

export interface MaterialMetadata {
  id: string;
  serialNumber: string;
  category: string;
  baseMetal: BaseMetalType;
  /** Empty unless a catalogue preset or the user set it; never inferred from composition. */
  standardDesignation: string;
  /** "catalogue": from a preset (cleared once the composition is edited away from it); "user": typed by the user. */
  standardDesignationSource?: "catalogue" | "user";
  manufacturingRoute: string;
  condition: string;
  leadMetallurgist: string;
  organization: string;
  notes: string;
  createdDate: string;
  lastModified: number;
  source: string;
  density_gcm3: number;
  tags?: string[];
  [key: string]: any;
}

export interface MaterialSpecimen {
  id: string;
  name: string;
  chemicalFormula: string;
  composition: Record<string, number>; // Element symbol -> wt%
  unit: "wt_pct" | "at_pct";
  metadata: MaterialMetadata;

  // Thermodynamic and mechanical properties: null = unavailable (no validated composition-to-property model; see
  // COMPOSITION_PROPERTY_UNAVAILABLE_NOTE). Never filled from composition heuristics.
  liquidus_C: number | null;
  solidus_C: number | null;
  freezingRange_C: number | null;
  solvus_C: number | null;
  stablePhases: string[];

  yieldStrength_25C_MPa: number | null;
  uts_25C_MPa: number | null;
  youngsModulus_GPa: number | null;
  elongation_pct: number | null;
  /**
   * Never a measurement: an estimate from the (itself composition-based) yield strength for non-austenitic
   * hypoeutectoid steels only (Pavlina & Van Tyne 2008), otherwise null (unavailable). See hardnessHVNote.
   */
  hardness_HV: number | null;
  hardnessHVStatus?: HardnessHVEstimateStatus;
  /** Source and validity range of hardness_HV, or the reason it is unavailable. */
  hardnessHVNote?: string;

  // 3D LPBF Additive & Thermal Parameters
  lpbf: {
    recommendedLaserPower_W: number;
    recommendedScanSpeed_mms: number;
    recommendedHatch_um: number;
    recommendedLayer_um: number;
    recommendedPreheatTemp_C: number;
    thermalConductivity_k_WmK: number;
    density_rho_kgm3: number;
    specificHeat_Cp_JkgK: number;
    laserAbsorptivity: number;
    thermalExpansion_CTE_10e6: number;
    criticalGradient_G_Km: number;
    hotTearingSusceptibility: "Low" | "Moderate" | "High";
    crackingMechanism: string;
    mitigationRecommendation: string;
  };

  // Crystallography & XRD
  xrd: {
    crystalSystem: "FCC" | "BCC" | "HCP" | "Tetragonal" | "Other";
    spaceGroup: string;
    latticeA_A: number;
    latticeC_A?: number;
    targetPhases: string[];
    microstrain_pct: number;
    crystalliteSize_nm: number;
  };

  // Provenance & Source Tab
  sourceTab: string;
  lastModified: number;
  isCustomModified: boolean;
}

// Alias interface for backward compatibility
export type ActiveSpecimenState = MaterialSpecimen;

export interface MaterialStore {
  activeMaterialSpecimen: MaterialSpecimen;
  // Alias for backward compatibility
  activeSpecimen: MaterialSpecimen;
  savedSpecimens: MaterialSpecimen[];

  // Core Actions
  updateComposition: (
    newComposition: Record<string, number> | ((prev: Record<string, number>) => Record<string, number>),
    customName?: string,
    metadataPatch?: Partial<MaterialMetadata>,
    sourceTab?: string
  ) => void;
  setElement: (element: string, percentage: number) => void;
  removeElement: (element: string) => void;
  normalizeComposition: () => void;
  updateName: (name: string) => void;
  updateMetadata: (metadataPatch: Partial<MaterialMetadata>) => void;
  setActiveMaterialSpecimen: (specimen: Partial<MaterialSpecimen>) => void;
  setSpecimen: (specimen: Partial<MaterialSpecimen>) => void;
  loadPreset: (presetId: string) => void;
  resetToDefault: () => void;
  saveCurrentSpecimen: (notes?: string) => void;
  exportAsJSON: () => string;
  importFromJSON: (jsonString: string) => boolean;
}

// ----------------------------------------------------------------------
// Physics Calculation Helpers
// ----------------------------------------------------------------------

function isValidCompositionInput(value: unknown): value is Record<string, number> {
  return !!value && typeof value === "object" && !Array.isArray(value)
    && Object.entries(value).every(([element, percentage]) => element.trim().length > 0
      && typeof percentage === "number" && Number.isFinite(percentage)
      && percentage >= 0 && percentage <= 100);
}

/** Tabulated elemental densities; single source in compositionPropertyAvailability. */
export const ELEMENT_DENSITIES = ELEMENTAL_DENSITY_GCM3;

export function detectBaseMetal(comp: Record<string, number>): BaseMetalType {
  let highestElem = "Ni";
  let maxPct = -1;
  for (const [elem, pct] of Object.entries(comp)) {
    if (typeof pct === "number" && pct > maxPct) {
      maxPct = pct;
      highestElem = elem;
    }
  }

  if (highestElem === "Ni") return "Ni";
  if (highestElem === "Fe") return "Fe";
  if (highestElem === "Ti") return "Ti";
  if (highestElem === "Al") return "Al";
  if (highestElem === "Cu") return "Cu";
  if (highestElem === "Co") return "Co";
  if (highestElem === "Mg") return "Mg";
  if (["W", "Mo", "Ta", "Nb", "Re"].includes(highestElem)) return "Refractory";
  return "Other";
}

/**
 * Internal LPBF-input density only (feeds lpbf.density_rho_kgm3 and must stay stable): it uses 8.0 g/cm3 for an
 * element without a tabulated density and 8.2 g/cm3 for an empty composition. These fallbacks are NOT for display;
 * screens use ruleOfMixturesDensity(), which reports 'unavailable' instead.
 */
export function calculateDensity(comp: Record<string, number>): number {
  let totalMass = 0;
  let totalVolume = 0;

  for (const [elem, pct] of Object.entries(comp)) {
    if (typeof pct === "number" && pct > 0) {
      totalMass += pct;
      const rho = ELEMENT_DENSITIES[elem] || 8.0;
      totalVolume += pct / rho;
    }
  }

  if (totalVolume <= 0 || totalMass <= 0) return 8.2;
  return parseFloat((totalMass / totalVolume).toFixed(3));
}

export function generateFormula(comp: Record<string, number>, baseMetal: BaseMetalType): string {
  const entries = Object.entries(comp)
    .filter(([_, pct]) => typeof pct === "number" && pct > 0.05)
    .sort((a, b) => b[1] - a[1]);

  const baseEntry = entries.find(([el]) => el === baseMetal);
  const otherEntries = entries.filter(([el]) => el !== baseMetal);

  const parts: string[] = [];
  if (baseEntry) {
    parts.push(baseEntry[0]);
  }

  for (const [elem, pct] of otherEntries) {
    const formatted = Number.isInteger(pct) ? `${pct}` : pct.toFixed(1).replace(/\.0$/, "");
    parts.push(`${formatted}${elem}`);
  }

  return parts.join("-");
}

export function deriveProperties(
  composition: Record<string, number>,
  customName?: string,
  forcedBase?: BaseMetalType,
  existingMetadata?: Partial<MaterialMetadata>
): Omit<MaterialSpecimen, "id" | "sourceTab" | "lastModified" | "isCustomModified"> {
  const baseMetal = forcedBase || detectBaseMetal(composition);
  const density_gcm3 = calculateDensity(composition);
  const chemicalFormula = generateFormula(composition, baseMetal);

  const cr = composition["Cr"] || 0;
  const mo = composition["Mo"] || 0;
  const w = composition["W"] || 0;
  const ta = composition["Ta"] || 0;
  const al = composition["Al"] || 0;
  const ti = composition["Ti"] || 0;
  const nb = composition["Nb"] || 0;
  const c = composition["C"] || 0;
  const v = composition["V"] || 0;
  const fe = composition["Fe"] || 0;

  // Liquidus/solidus/solvus, yield, UTS, modulus and elongation are no longer filled by per-base linear formulas
  // (e.g. Ni yield 320 + 85 x gamma-prime formers, steel 750 + 900 C so pure Fe showed 750 MPa, Al solidus a constant
  // 570 degC): none had a source. See COMPOSITION_PROPERTY_UNAVAILABLE_NOTE.
  // A standard designation is never inferred from composition thresholds (any Ni alloy with Nb > 2.5 used to become
  // "UNS N07718 / AMS 5662"): only a catalogue preset or the user sets one.
  let category = existingMetadata?.category || materialCategoryForBase(baseMetal);
  const standardDesignation = existingMetadata?.standardDesignation ?? "";
  let crystalSystem: "FCC" | "BCC" | "HCP" | "Tetragonal" | "Other" = "FCC";
  let spaceGroup = "Fm-3m (225)";
  let latticeA_A = 3.595;
  let latticeC_A: number | undefined = undefined;
  let targetPhases: string[] = ["austenite-fcc", "gamma-prime-ni3al"];

  if (baseMetal === "Ni") {
    category = "Nickel Superalloy";
    const gammaPrimeFormers = al + ti + ta + nb;
    crystalSystem = "FCC";
    spaceGroup = "Fm-3m (225)";
    latticeA_A = parseFloat((3.524 + cr * 0.0018 + mo * 0.0035 + w * 0.0038 + ta * 0.0045 + al * 0.0022 + ti * 0.003).toFixed(3));
    if (nb > 2.5) {
      targetPhases = ["austenite-fcc", "gamma-double-prime", "laves-fe2nb"];
    } else if (gammaPrimeFormers > 3.0) {
      targetPhases = ["austenite-fcc", "gamma-prime-ni3al", "carbide-mc"];
    } else {
      targetPhases = ["austenite-fcc", "carbide-m23c6"];
    }
  } else if (baseMetal === "Ti") {
    category = "Titanium Alloy";
    const moEquiv = mo + 0.67 * v + 0.44 * (composition["W"] || 0) + 0.28 * nb + 1.25 * cr + 1.25 * fe;
    if (moEquiv > 10) {
      crystalSystem = "BCC";
      spaceGroup = "Im-3m (229)";
      latticeA_A = 3.31;
      targetPhases = ["beta-bcc", "alpha-prime-martensite"];
    } else {
      crystalSystem = "HCP";
      spaceGroup = "P6_3/mmc (194)";
      latticeA_A = 2.95;
      latticeC_A = 4.68;
      targetPhases = ["alpha-hcp", "beta-bcc"];
    }
  } else if (baseMetal === "Fe") {
    category = "Steels & Irons";
    // Si defaults to 0: a Si-free composition gave NaN here and skipped the austenitic branch below.
    const crEq = cr + mo * 1.5 + (composition["Si"] || 0) * 1.5 + (composition["Nb"] || 0) * 0.5;
    // Parenthesised: `Ni || 0 + ...` counted only Ni whenever Ni was present (C, N, Mn were dropped).
    const niEq = (composition["Ni"] || 0) + c * 30 + (composition["N"] || 0) * 30 + (composition["Mn"] || 0) * 0.5;
    if (niEq > 8 && crEq > 16) {
      crystalSystem = "FCC";
      spaceGroup = "Fm-3m (225)";
      latticeA_A = 3.595;
      targetPhases = ["austenite-fcc", "delta-ferrite"];
    } else {
      crystalSystem = "BCC";
      spaceGroup = "Im-3m (229)";
      latticeA_A = 2.866;
      targetPhases = ["martensite-bct", "retained-austenite"];
    }
  } else if (baseMetal === "Al") {
    category = "Aluminum Alloys";
    crystalSystem = "FCC";
    spaceGroup = "Fm-3m (225)";
    latticeA_A = 4.049;
    targetPhases = ["alpha-al-fcc", "eutectic-si", "mg2si-precipitates"];
  }

  // HV is never measured here, and without a yield strength it is Unavailable for every class.
  const hardnessEstimate = estimateSpecimenHardnessHV({
    baseMetal,
    crystalSystem,
    composition,
    yieldStrength_MPa: null,
  });

  // One LPBF block for both stores: the shared specimen store's derivation (it feeds the live LPBF vector on preset
  // load, so its values stay as they are). This store used to keep a second, diverging copy.
  const { lpbf: sharedLpbf } = deriveSpecimenProperties(composition, customName, baseMetal);

  const name = customName || existingMetadata?.name || `${chemicalFormula} Specimen`;

  const metadata: MaterialMetadata = {
    id: existingMetadata?.id || `specimen-${Date.now()}`,
    serialNumber: existingMetadata?.serialNumber || "",
    category,
    baseMetal,
    standardDesignation,
    ...(existingMetadata?.standardDesignationSource ? { standardDesignationSource: existingMetadata.standardDesignationSource } : {}),
    manufacturingRoute: existingMetadata?.manufacturingRoute || "Unspecified",
    condition: existingMetadata?.condition || "Unspecified",
    leadMetallurgist: existingMetadata?.leadMetallurgist || "",
    organization: existingMetadata?.organization || "",
    notes: existingMetadata?.notes || `Composition record (${chemicalFormula})`,
    createdDate: existingMetadata?.createdDate || new Date().toISOString().split("T")[0],
    lastModified: Date.now(),
    source: existingMetadata?.source || "Alloy Builder composition editor",
    density_gcm3,
    tags: existingMetadata?.tags || [category, baseMetal],
  };

  return {
    name,
    chemicalFormula,
    composition,
    unit: "wt_pct",
    metadata,
    liquidus_C: null,
    solidus_C: null,
    freezingRange_C: null,
    solvus_C: null,
    stablePhases: targetPhases,
    yieldStrength_25C_MPa: null,
    uts_25C_MPa: null,
    youngsModulus_GPa: null,
    elongation_pct: null,
    hardness_HV: hardnessEstimate.hv,
    hardnessHVStatus: hardnessEstimate.status,
    hardnessHVNote: hardnessEstimate.note,
    lpbf: {
      recommendedLaserPower_W: sharedLpbf.recommendedLaserPower_W,
      recommendedScanSpeed_mms: sharedLpbf.recommendedScanSpeed_mms,
      recommendedHatch_um: sharedLpbf.recommendedHatch_um,
      recommendedLayer_um: sharedLpbf.recommendedLayer_um,
      recommendedPreheatTemp_C: sharedLpbf.recommendedPreheatTemp_C,
      thermalConductivity_k_WmK: sharedLpbf.thermalConductivity_k_WmK,
      density_rho_kgm3: sharedLpbf.density_rho_kgm3,
      specificHeat_Cp_JkgK: sharedLpbf.specificHeat_Cp_JkgK,
      laserAbsorptivity: sharedLpbf.laserAbsorptivity,
      thermalExpansion_CTE_10e6: sharedLpbf.thermalExpansion_CTE_10e6,
      criticalGradient_G_Km: sharedLpbf.criticalGradient_G_Km,
      hotTearingSusceptibility: sharedLpbf.hotTearingSusceptibility,
      crackingMechanism: sharedLpbf.crackingMechanism,
      mitigationRecommendation: sharedLpbf.mitigationRecommendation,
    },
    xrd: {
      crystalSystem,
      spaceGroup,
      latticeA_A,
      latticeC_A,
      targetPhases,
      microstrain_pct: 0.22,
      crystalliteSize_nm: 28,
    },
  };
}

export const MATERIAL_STORE_VERSION = 2;

/** Recompute the hardness fields of a stored specimen (used for persisted records and atomic-percent edits). */
export function withHardnessEstimate(specimen: MaterialSpecimen): MaterialSpecimen {
  const e = estimateSpecimenHardnessHV({
    baseMetal: specimen.metadata?.baseMetal,
    crystalSystem: specimen.xrd?.crystalSystem,
    composition: specimen.composition,
    unit: specimen.unit,
    yieldStrength_MPa: specimen.yieldStrength_25C_MPa,
  });
  return { ...specimen, hardness_HV: e.hv, hardnessHVStatus: e.status, hardnessHVNote: e.note };
}

/** Designations the removed threshold rules assigned from composition (plus the old default preset's non-standard). */
const AUTO_ASSIGNED_DESIGNATIONS = new Set([
  "UNS N07718 / AMS 5662",
  "AMS 5873 (René 41 Class)",
  "Hastelloy X Class",
  "ASTM B348 / AMS 4928",
  "AISI 316L / ASTM A276",
  "Alloy Steel / Tool Steel",
  "AlSi10Mg / EN AC-43000",
  "Aerospace High-T Turbine Rotor",
]);

function sameComposition(a: Record<string, number> | undefined, b: Record<string, number>): boolean {
  if (!a || typeof a !== "object") return false;
  const keysA = Object.keys(a).filter((k) => a[k] !== 0);
  const keysB = Object.keys(b).filter((k) => b[k] !== 0);
  return keysA.length === keysB.length && keysB.every((k) => a[k] === b[k]);
}

/** The catalogue preset whose composition this is exactly, if any. */
export function catalogueDesignationFor(composition: Record<string, number> | undefined): string | null {
  for (const preset of Object.values(MATERIAL_PRESETS)) {
    if (sameComposition(composition, preset.composition)) return preset.standard;
  }
  return null;
}

/**
 * A catalogue designation belongs to the catalogue composition: editing the composition away from it clears the
 * designation (unless this edit sets one). A user-typed designation is the user's claim and is kept.
 */
/** Suffix added to a catalogue preset name once the composition is edited away from that catalogue alloy. */
export const MODIFIED_CATALOGUE_NAME_SUFFIX = " (modified, not the catalogue alloy)";

/**
 * The preset names carry the catalogue identity (e.g. "Inconel 718 (AMS 5662)"). When an edit clears the catalogue
 * designation and the caller keeps that name, mark it so the name does not keep claiming the catalogue alloy.
 */
export function nameAfterCompositionEdit(
  current: Pick<MaterialSpecimen, "name" | "metadata">,
  requestedName: string | undefined,
  metadataPatch: Partial<MaterialMetadata> | undefined,
  designationPatch: Partial<MaterialMetadata>
): string {
  const name = requestedName || current.name;
  const catalogueCleared = current.metadata?.standardDesignationSource === "catalogue"
    && !(metadataPatch && "standardDesignation" in metadataPatch)
    && designationPatch.standardDesignation === "";
  if (!catalogueCleared || name !== current.name || name.endsWith(MODIFIED_CATALOGUE_NAME_SUFFIX)) return name;
  return `${name}${MODIFIED_CATALOGUE_NAME_SUFFIX}`;
}

export function designationAfterCompositionEdit(
  current: Pick<MaterialSpecimen, "composition" | "metadata">,
  nextComposition: Record<string, number>,
  metadataPatch?: Partial<MaterialMetadata>
): Partial<MaterialMetadata> {
  if (metadataPatch && "standardDesignation" in metadataPatch) {
    if ("standardDesignationSource" in metadataPatch) return {};
    // A designation handed in without a source (e.g. Digital Twin Hub push) is the user's, not the catalogue's; an
    // empty or "Unresolved" one carries no source at all.
    const designation = (metadataPatch.standardDesignation ?? "").trim();
    return designation && designation !== "Unresolved"
      ? { standardDesignationSource: "user" }
      : { standardDesignation: "", standardDesignationSource: undefined };
  }
  if (current.metadata?.standardDesignationSource !== "catalogue") return {};
  if (sameComposition(current.composition, nextComposition)) return {};
  return { standardDesignation: "", standardDesignationSource: undefined };
}

/**
 * Version 2: drop the heuristic property numbers and the designations the threshold rules made up. A record whose
 * composition is exactly a catalogue preset keeps that preset's designation; any other designation the rules could
 * have produced is cleared; anything else (typed by the user) is kept.
 */
function withoutInventedDesignation(specimen: MaterialSpecimen): MaterialSpecimen {
  const metadata = specimen.metadata;
  if (!metadata || typeof metadata !== "object") return specimen;
  const catalogue = catalogueDesignationFor(specimen.composition);
  if (catalogue !== null && specimen.unit !== "at_pct") {
    return { ...specimen, metadata: { ...metadata, standardDesignation: catalogue, standardDesignationSource: "catalogue" } };
  }
  if (AUTO_ASSIGNED_DESIGNATIONS.has(metadata.standardDesignation)) {
    const cleared: MaterialMetadata = { ...metadata, standardDesignation: "" };
    delete cleared.standardDesignationSource;
    return { ...specimen, metadata: cleared };
  }
  return specimen;
}

/**
 * Version 1 recomputed hardness_HV (the removed unsourced YS/x rules). Version 2 nulls the composition-heuristic
 * properties (liquidus ... elongation), recomputes HV without them (Unavailable) and clears invented designations.
 */
export function migrateMaterialStoreState(persisted: unknown, version: number): unknown {
  if (version >= MATERIAL_STORE_VERSION || !persisted || typeof persisted !== "object") return persisted;
  const state = persisted as Record<string, unknown>;
  const isSpecimenLike = (s: unknown) =>
    !!s && typeof s === "object" && !Array.isArray(s)
    && ("hardness_HV" in (s as object) || "yieldStrength_25C_MPa" in (s as object) || "composition" in (s as object));
  // Every specimen-like entry is recomputed; one without a yield strength gets Unavailable instead of keeping a stale
  // HV. Non-objects pass through.
  const fix = (s: unknown) =>
    isSpecimenLike(s)
      ? withHardnessEstimate(withoutInventedDesignation(withoutCompositionHeuristicProperties(s as MaterialSpecimen)))
      : s;
  return {
    ...state,
    ...(state.activeMaterialSpecimen ? { activeMaterialSpecimen: fix(state.activeMaterialSpecimen) } : {}),
    ...(state.activeSpecimen ? { activeSpecimen: fix(state.activeSpecimen) } : {}),
    ...(Array.isArray(state.savedSpecimens) ? { savedSpecimens: state.savedSpecimens.map(fix) } : {}),
  };
}

/**
 * Persisted data over the initial state. activeSpecimen always mirrors activeMaterialSpecimen (an old blob may lack
 * one of them); actions always come from the current state.
 */
export function mergeMaterialStoreState(persisted: unknown, current: MaterialStore): MaterialStore {
  if (!persisted || typeof persisted !== "object" || Array.isArray(persisted)) return current;
  const p = persisted as Partial<MaterialStore>;
  const asSpecimen = (s: unknown) => isPersistableSpecimen(s) ? s : undefined;
  const active = asSpecimen(p.activeMaterialSpecimen) ?? asSpecimen(p.activeSpecimen) ?? current.activeMaterialSpecimen;
  return {
    ...current,
    activeMaterialSpecimen: active,
    activeSpecimen: active,
    savedSpecimens: Array.isArray(p.savedSpecimens)
      ? p.savedSpecimens.filter(isPersistableSpecimen)
      : current.savedSpecimens,
  };
}

/** Persisted specimens must carry a non-empty, bounded composition before migration or hydration can use them. */
function isPersistableSpecimen(value: unknown): value is MaterialSpecimen {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  try {
    const specimen = value as Partial<MaterialSpecimen>;
    return typeof specimen.id === "string"
      && typeof specimen.name === "string"
      && (specimen.unit === "wt_pct" || specimen.unit === "at_pct")
      && !!specimen.metadata
      && typeof specimen.metadata === "object"
      && !Array.isArray(specimen.metadata)
      && isNonEmptyValidComposition(specimen.composition);
  } catch {
    // Malformed legacy objects (including throwing accessors) are discarded without deriving properties.
    return false;
  }
}

function isNonEmptyValidComposition(value: unknown): value is Record<string, number> {
  try {
    return isValidCompositionInput(value) && Object.keys(value).length > 0;
  } catch {
    return false;
  }
}

// ----------------------------------------------------------------------
// Universal Standard Material Presets
// ----------------------------------------------------------------------

export const MATERIAL_PRESETS: Record<
  string,
  {
    name: string;
    category: string;
    base: BaseMetalType;
    standard: string;
    description: string;
    composition: Record<string, number>;
  }
> = {
  "in718": {
    name: "Inconel 718 (AMS 5662)",
    category: "Nickel Superalloy",
    base: "Ni",
    standard: "UNS N07718 / AMS 5662",
    description: "Precipitation-hardened nickel-chromium superalloy with exceptional creep rupture strength up to 700°C.",
    composition: {
      Ni: 53.0,
      Fe: 18.5,
      Cr: 19.0,
      Nb: 5.1,
      Mo: 3.05,
      Ti: 0.9,
      Al: 0.5,
      C: 0.04,
      Co: 0.1,
      Si: 0.2,
      Mn: 0.2,
    },
  },
  "custom-ni-superalloy": {
    name: "Custom Ni Superalloy (example composition)",
    category: "Nickel Superalloy",
    base: "Ni",
    // Not a catalogue alloy: no standard designation.
    standard: "",
    description: "Example gamma-prime-former-rich Ni composition for editing; not a catalogue alloy and not characterised.",
    composition: {
      Ni: 58.2,
      Cr: 16.5,
      Co: 8.5,
      Mo: 1.8,
      W: 2.6,
      Ta: 1.8,
      Al: 3.5,
      Ti: 3.4,
      C: 0.05,
      B: 0.015,
      Zr: 0.03,
    },
  },
  "ti64-gr5": {
    name: "Ti-6Al-4V Grade 5",
    category: "Titanium Alloy",
    base: "Ti",
    standard: "ASTM B348 / AMS 4928",
    description: "Workhorse aerospace alpha-beta titanium alloy combining high specific strength with excellent corrosion immunity.",
    composition: {
      Ti: 89.2,
      Al: 6.25,
      V: 4.1,
      Fe: 0.25,
      O: 0.18,
      C: 0.02,
    },
  },
  "ss316l": {
    name: "AISI 316L Stainless Steel",
    category: "Steels & Irons",
    base: "Fe",
    standard: "ASTM A276 / AMS 5653",
    description: "Molybdenum-bearing austenitic stainless steel offering superior pitting resistance and weldability.",
    composition: {
      Fe: 65.5,
      Cr: 17.5,
      Ni: 12.0,
      Mo: 2.4,
      Mn: 1.8,
      Si: 0.6,
      C: 0.02,
    },
  },
  "alsi10mg": {
    name: "AlSi10Mg Additive Lightweight",
    category: "Aluminum Alloys",
    base: "Al",
    standard: "EN AC-43000 / ASTM F3318",
    description: "Near-eutectic aluminum-silicon casting alloy with high thermal conductivity and rapid hardening kinetics.",
    composition: {
      Al: 89.5,
      Si: 9.8,
      Mg: 0.45,
      Fe: 0.20,
      Mn: 0.05,
    },
  },
  "cocr-bio": {
    name: "Co-Cr-Mo Orthopedic Implant Alloy",
    category: "Cobalt / Bio",
    base: "Co",
    standard: "ASTM F75 / ISO 5832-4",
    description: "High-wear and biocompatible cobalt superalloy designed for orthopedic arthroplasty joint implants.",
    composition: {
      Co: 64.0,
      Cr: 28.5,
      Mo: 6.0,
      Mn: 0.8,
      Si: 0.5,
      C: 0.2,
    },
  },
  "maraging300": {
    name: "Maraging 300 Ultra-High Strength Steel",
    category: "Steels & Irons",
    base: "Fe",
    standard: "AMS 6514 / Vascomax 300",
    description: "Carbon-free martensitic steel strengthened by intermetallic nickel-cobalt-molybdenum-titanium precipitates.",
    composition: {
      Fe: 67.5,
      Ni: 18.5,
      Co: 9.0,
      Mo: 4.8,
      Ti: 0.6,
      Al: 0.1,
      C: 0.01,
    },
  },
  "hastelloy-x": {
    name: "Hastelloy X Combustion Alloy",
    category: "Nickel Superalloy",
    base: "Ni",
    standard: "AMS 5754 / UNS N06002",
    description: "Nickel-chromium-iron-molybdenum alloy with exceptional oxidation resistance in industrial gas turbine combustion liners.",
    composition: {
      Ni: 47.0,
      Cr: 22.0,
      Fe: 18.0,
      Mo: 9.0,
      Co: 1.5,
      W: 0.6,
      C: 0.10,
    },
  },
};

// Initial default specimen
const DEFAULT_PRESET_KEY = "custom-ni-superalloy";
const DEFAULT_PRESET = MATERIAL_PRESETS[DEFAULT_PRESET_KEY];
const DEFAULT_DERIVED = deriveProperties(
  DEFAULT_PRESET.composition,
  DEFAULT_PRESET.name,
  DEFAULT_PRESET.base,
  {
    category: DEFAULT_PRESET.category,
    standardDesignation: DEFAULT_PRESET.standard,
    standardDesignationSource: "catalogue",
    notes: DEFAULT_PRESET.description,
  }
);

export const INITIAL_MATERIAL_SPECIMEN: MaterialSpecimen = {
  id: "specimen-universal-rene-850",
  ...DEFAULT_DERIVED,
  sourceTab: "Alloy Formulator (Tab 1)",
  lastModified: Date.now(),
  isCustomModified: false,
};

// ----------------------------------------------------------------------
// Zustand Store Implementation
// ----------------------------------------------------------------------

export const useMaterialStore = create<MaterialStore>()(
  persist(
    (set, get) => ({
      activeMaterialSpecimen: INITIAL_MATERIAL_SPECIMEN,
      // Plain field kept in sync by every setter. A getter here (`get activeSpecimen() { return get()... }`) threw
      // while zustand spread the initial state during first hydration, so persisted state (saved specimens) was
      // discarded and the version migration never ran.
      activeSpecimen: INITIAL_MATERIAL_SPECIMEN,
      savedSpecimens: [INITIAL_MATERIAL_SPECIMEN],

      updateComposition: (newComposition, customName, metadataPatch, sourceTab = "Alloy Formulator (Tab 1)") => {
        const current = get().activeMaterialSpecimen;
        const resolvedComp = typeof newComposition === "function" ? newComposition({ ...current.composition }) : newComposition;
        if (!isValidCompositionInput(resolvedComp)) return;
        const designationPatch = designationAfterCompositionEdit(current, resolvedComp, metadataPatch);
        const nextName = nameAfterCompositionEdit(current, customName, metadataPatch, designationPatch);
        // Atomic-percent edits retain their unit and identity; weight-percent models are not evaluated.
        if (current.unit === "at_pct") {
          const next: MaterialSpecimen = withHardnessEstimate({...current,composition:resolvedComp,name:nextName,sourceTab,lastModified:Date.now(),isCustomModified:true,metadata:{...current.metadata,...metadataPatch,...designationPatch,source:"Atomic-percent composition; weight-percent property estimates unresolved"}});
          set({activeMaterialSpecimen:next,activeSpecimen:next});
          return;
        }
        const updatedMetadata = { ...current.metadata, ...metadataPatch, ...designationPatch, lastModified: Date.now() };
        const derived = deriveProperties(resolvedComp, nextName, undefined, updatedMetadata);

        const nextSpecimen: MaterialSpecimen = {
          id: current.id.startsWith("specimen-") ? current.id : `specimen-${Date.now()}`,
          ...derived,
          sourceTab,
          lastModified: Date.now(),
          isCustomModified: true,
        };

        set({
          activeMaterialSpecimen: nextSpecimen,
          activeSpecimen: nextSpecimen,
        });

        // Publish to global pipeline so existing listeners receive update
        try {
          const pipelinePayload: PipelineMaterialPayload = {
            id: nextSpecimen.id,
            name: nextSpecimen.name,
            category: nextSpecimen.metadata.category,
            standard: nextSpecimen.metadata.standardDesignation,
            sourceModule: sourceTab,
            timestamp: Date.now(),
            composition: nextSpecimen.composition,
            compositionUnit: nextSpecimen.unit,
            compositionInterpretation: "nominal",
            baseMetal: nextSpecimen.metadata.baseMetal as any,
            // null: unavailable (no validated composition-to-property model), never a heuristic number.
            yieldStrength: nextSpecimen.yieldStrength_25C_MPa,
            tensileStrength: nextSpecimen.uts_25C_MPa,
            youngsModulus: nextSpecimen.youngsModulus_GPa,
            density: nextSpecimen.metadata.density_gcm3,
            elongation: nextSpecimen.elongation_pct,
            // Estimate or unavailable, never measured: the note carries the source/range or the reason.
            hardness: nextSpecimen.hardnessHVNote ?? (nextSpecimen.hardness_HV === null ? "Unavailable" : `${nextSpecimen.hardness_HV} HV (estimate, not measured)`),
            hardnessHV: nextSpecimen.hardness_HV,
            hardnessHVSource: nextSpecimen.hardness_HV === null ? "unavailable" : "estimate-from-yield",
            poissonsRatio: 0.31,
            thermalConductivity: nextSpecimen.lpbf.thermalConductivity_k_WmK,
            kineticProfile: {
              id: nextSpecimen.id,
              name: nextSpecimen.name,
              baseMetal: (["Ni", "Fe", "Ti", "Al"].includes(nextSpecimen.metadata.baseMetal) ? nextSpecimen.metadata.baseMetal : "Ni") as any,
              standardRef: nextSpecimen.metadata.standardDesignation,
              initialGrainSize_um: 25,
              grainGrowthExponent_n: 2.1,
              activationEnergy_kJ_mol: 285,
              preExponential_k0: 1.2e-4,
              solvusTemp_C: nextSpecimen.solvus_C,
              // Was solvus + 50 (and null + 50 = 50 once solvus became unavailable): not derived.
              criticalTemp_Ac3_C: null,
              solidusTemp_C: nextSpecimen.solidus_C,
              precipitateType: "Intermetallic / Carbides",
              initialPrecipVolFrac: 15,
              precipMeanRadius_nm: 25,
              // Unsourced constants (750 MPa·µm^0.5, 65 MPa·√m, L/LT/ST factors) removed: unavailable.
              hallPetch_ky_MPa_um05: null,
            } as any,
            hardnessProfile: {
              id: nextSpecimen.id,
              name: nextSpecimen.name,
              category: nextSpecimen.metadata.category as any,
              crystalStructure: nextSpecimen.xrd.crystalSystem as any,
              defaultHardnessHV: nextSpecimen.hardness_HV ?? undefined,
              hardnessHV: nextSpecimen.hardness_HV,
              measuredYield_MPa: nextSpecimen.yieldStrength_25C_MPa,
              measuredUTS_MPa: nextSpecimen.uts_25C_MPa,
              workHardeningExponent_n: 0.15,
              // Was UTS x 1.45 on the heuristic UTS: unavailable.
              strengthCoefficient_K_MPa: null,
              cahoon_m: 0.33,
              tabor_c: 2.95,
              taborConstraintFactor_c: 2.95,
              hollomon_alpha: 0.002,
              elasticModulus_E_GPa: nextSpecimen.youngsModulus_GPa,
              youngsModulus_E_GPa: nextSpecimen.youngsModulus_GPa,
              poissonsRatio_nu: 0.31,
              poissonsRatio: 0.31,
              uniformElongation_pct: nextSpecimen.elongation_pct,
              fractureToughness_K1c_MPa_sqrt_m: null,
              estimatedK1c_MPam05: null,
              anisotropyFactors: null,
              description: `Shared specimen composition (${nextSpecimen.chemicalFormula})`,
              standardRef: nextSpecimen.metadata.standardDesignation,
            } as any,
            xrdProfile: {
              crystalSystem: nextSpecimen.xrd.crystalSystem,
              spaceGroup: nextSpecimen.xrd.spaceGroup,
              latticeA_A: nextSpecimen.xrd.latticeA_A,
              latticeC_A: nextSpecimen.xrd.latticeC_A,
              primaryPhases: nextSpecimen.stablePhases,
              peaks: [],
            },
            icmeProfile: {
              liquidusTemp_C: nextSpecimen.liquidus_C,
              solidusTemp_C: nextSpecimen.solidus_C,
              solvusTemp_C: nextSpecimen.solvus_C,
              dominantPhases: nextSpecimen.stablePhases,
            },
          };
          setActivePipelineMaterial(pipelinePayload);
        } catch (e) {
          console.warn("[MaterialStore] Pipeline sync skipped", e);
        }
      },

      setElement: (element, percentage) => {
        if (!element.trim() || !Number.isFinite(percentage) || percentage < 0 || percentage > 100) return;
        const current = get().activeMaterialSpecimen;
        const newComp = { ...current.composition };
        if (percentage === 0) {
          delete newComp[element];
        } else {
          newComp[element] = parseFloat(percentage.toFixed(3));
        }
        get().updateComposition(newComp, current.name, { lastModified: Date.now() });
      },

      removeElement: (element) => {
        const current = get().activeMaterialSpecimen;
        const newComp = { ...current.composition };
        delete newComp[element];
        get().updateComposition(newComp, current.name, { lastModified: Date.now() });
      },

      normalizeComposition: () => {
        const current = get().activeMaterialSpecimen;
        if (!isValidCompositionInput(current.composition)) return;
        const total = Object.values(current.composition).reduce((acc, val) => acc + (typeof val === "number" ? val : 0), 0);
        if (!Number.isFinite(total) || total <= 0) return;
        const factor = 100 / total;
        const normalized: Record<string, number> = {};
        for (const [el, pct] of Object.entries(current.composition)) {
          normalized[el] = parseFloat((pct * factor).toFixed(2));
        }
        get().updateComposition(normalized, current.name);
      },

      updateName: (name) => {
        const current = get().activeMaterialSpecimen;
        const next: MaterialSpecimen = {
          ...current,
          name,
          metadata: {
            ...current.metadata,
            name,
            lastModified: Date.now(),
          },
          lastModified: Date.now(),
          isCustomModified: true,
        };
        set({ activeMaterialSpecimen: next, activeSpecimen: next });
      },

      updateMetadata: (metadataPatch) => {
        const current = get().activeMaterialSpecimen;
        const typedDesignation =
          "standardDesignation" in metadataPatch && !("standardDesignationSource" in metadataPatch)
            ? { standardDesignationSource: "user" as const }
            : {};
        const nextMetadata: MaterialMetadata = {
          ...current.metadata,
          ...metadataPatch,
          ...typedDesignation,
          lastModified: Date.now(),
        };
        const next: MaterialSpecimen = {
          ...current,
          metadata: nextMetadata,
          lastModified: Date.now(),
        };
        set({ activeMaterialSpecimen: next, activeSpecimen: next });
      },

      setActiveMaterialSpecimen: (specimen) => {
        if (!specimen || typeof specimen !== "object" || Array.isArray(specimen)) return;
        if (Object.prototype.hasOwnProperty.call(specimen, "composition")
          && !isNonEmptyValidComposition(specimen.composition)) return;
        if (Object.prototype.hasOwnProperty.call(specimen, "metadata")
          && specimen.metadata !== undefined
          && (!specimen.metadata || typeof specimen.metadata !== "object" || Array.isArray(specimen.metadata))) return;
        const current = get().activeMaterialSpecimen;
        const merged: MaterialSpecimen = {
          ...current,
          ...specimen,
          metadata: {
            ...current.metadata,
            ...(specimen.metadata || {}),
            lastModified: Date.now(),
          },
          lastModified: Date.now(),
        };
        set({ activeMaterialSpecimen: merged, activeSpecimen: merged });
      },

      setSpecimen: (specimen) => {
        get().setActiveMaterialSpecimen(specimen);
      },

      loadPreset: (presetId) => {
        const preset = MATERIAL_PRESETS[presetId];
        if (!preset) return;
        const derived = deriveProperties(preset.composition, preset.name, preset.base, {
          category: preset.category,
          standardDesignation: preset.standard,
          standardDesignationSource: "catalogue",
          notes: preset.description,
        });
        const nextSpecimen: MaterialSpecimen = {
          id: `specimen-${presetId}-${Date.now()}`,
          ...derived,
          sourceTab: "Preset Selector",
          lastModified: Date.now(),
          isCustomModified: false,
        };
        set({ activeMaterialSpecimen: nextSpecimen, activeSpecimen: nextSpecimen });
        get().updateComposition(preset.composition, preset.name, {
          category: preset.category,
          standardDesignation: preset.standard,
          standardDesignationSource: "catalogue",
          notes: preset.description,
        }, "Preset Selector");
      },

      resetToDefault: () => {
        get().loadPreset(DEFAULT_PRESET_KEY);
      },

      saveCurrentSpecimen: (notes) => {
        const current = get().activeMaterialSpecimen;
        const snapshot: MaterialSpecimen = {
          ...current,
          id: `snapshot-${Date.now()}`,
          metadata: {
            ...current.metadata,
            notes: notes || current.metadata.notes,
            createdDate: new Date().toISOString().split("T")[0],
          },
          lastModified: Date.now(),
        };
        set((state) => ({
          savedSpecimens: [snapshot, ...state.savedSpecimens.filter((s) => s.id !== snapshot.id)],
        }));
      },

      exportAsJSON: () => {
        return JSON.stringify(get().activeMaterialSpecimen, null, 2);
      },

      importFromJSON: (jsonString) => {
        try {
          const parsed = JSON.parse(jsonString);
          if (parsed && isValidCompositionInput(parsed.composition)) {
            const derived = deriveProperties(
              parsed.composition,
              parsed.name || "Imported Specimen",
              parsed.metadata?.baseMetal || parsed.baseMetal,
              parsed.metadata
            );
            const imported: MaterialSpecimen = {
              id: parsed.id || `imported-${Date.now()}`,
              ...derived,
              ...parsed,
              sourceTab: "JSON Import",
              lastModified: Date.now(),
              isCustomModified: true,
            };
            set({ activeMaterialSpecimen: imported, activeSpecimen: imported });
            get().updateComposition(imported.composition, imported.name, imported.metadata, "JSON Import");
            return true;
          }
          return false;
        } catch {
          return false;
        }
      },
    }),
    {
      name: "metallix-material-specimen-store",
      version: MATERIAL_STORE_VERSION,
      migrate: (persisted, version) => migrateMaterialStoreState(persisted, version) as MaterialStore,
      merge: (persisted, current) => mergeMaterialStoreState(persisted, current),
    }
  )
);
