import { create } from "zustand";
import { persist } from "zustand/middleware";
import { setActivePipelineMaterial, PipelineMaterialPayload } from "../utils/materialDataPipeline";
import { estimateSpecimenHardnessHV, type HardnessHVEstimateStatus } from "../utils/hardnessStrengthEstimate";

export type BaseMetalType = "Ni" | "Fe" | "Ti" | "Al" | "Cu" | "Co" | "Mg" | "Refractory" | "Other";

export interface MaterialMetadata {
  id: string;
  serialNumber: string;
  category: string;
  baseMetal: BaseMetalType;
  standardDesignation: string;
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

  // Thermodynamic Properties
  liquidus_C: number;
  solidus_C: number;
  freezingRange_C: number;
  solvus_C: number;
  stablePhases: string[];

  // Mechanical Properties
  yieldStrength_25C_MPa: number;
  uts_25C_MPa: number;
  youngsModulus_GPa: number;
  elongation_pct: number;
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

export const ELEMENT_DENSITIES: Record<string, number> = {
  Ni: 8.908,
  Fe: 7.874,
  Cr: 7.19,
  Co: 8.90,
  Mo: 10.28,
  W: 19.25,
  Ta: 16.69,
  Al: 2.70,
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
  const density_rho_kgm3 = Math.round(density_gcm3 * 1000);
  const chemicalFormula = generateFormula(composition, baseMetal);

  const cr = composition["Cr"] || 0;
  const co = composition["Co"] || 0;
  const mo = composition["Mo"] || 0;
  const w = composition["W"] || 0;
  const ta = composition["Ta"] || 0;
  const al = composition["Al"] || 0;
  const ti = composition["Ti"] || 0;
  const nb = composition["Nb"] || 0;
  const fe = composition["Fe"] || 0;
  const c = composition["C"] || 0;
  const v = composition["V"] || 0;
  const mg = composition["Mg"] || 0;
  const si = composition["Si"] || 0;

  let category = existingMetadata?.category || "Nickel Superalloy";
  let standardDesignation = existingMetadata?.standardDesignation || "UNS N07718 / AMS 5662";
  let liquidus_C = 1340;
  let solidus_C = 1260;
  let solvus_C = 1120;
  let yieldStrength_25C_MPa = 1050;
  let uts_25C_MPa = 1350;
  let youngsModulus_GPa = 210;
  let elongation_pct = 16;
  let crystalSystem: "FCC" | "BCC" | "HCP" | "Tetragonal" | "Other" = "FCC";
  let spaceGroup = "Fm-3m (225)";
  let latticeA_A = 3.595;
  let latticeC_A: number | undefined = undefined;
  let targetPhases: string[] = ["austenite-fcc", "gamma-prime-ni3al"];
  let thermalConductivity_k_WmK = 11.5;
  let specificHeat_Cp_JkgK = 435;
  let recommendedLaserPower_W = 285;
  let recommendedScanSpeed_mms = 960;
  let recommendedPreheatTemp_C = 120;
  let hotTearingSusceptibility: "Low" | "Moderate" | "High" = "Moderate";
  let crackingMechanism = "Interdendritic solute segregation during terminal solidification";
  let mitigationRecommendation = "Maintain bed preheat >=150°C and optimize volumetric energy density (VED).";

  if (baseMetal === "Ni") {
    category = "Nickel Superalloy";
    const gammaPrimeFormers = al + ti + ta + nb;
    const refractoryMoW = mo + w;

    liquidus_C = Math.round(1455 - (cr * 2.5 + mo * 4 + al * 8 + ti * 10 + c * 40));
    solidus_C = Math.round(liquidus_C - (35 + gammaPrimeFormers * 4.5 + nb * 12 + c * 30));
    solvus_C = Math.min(solidus_C - 40, Math.round(950 + gammaPrimeFormers * 22 + refractoryMoW * 6));

    yieldStrength_25C_MPa = Math.round(320 + gammaPrimeFormers * 85 + refractoryMoW * 45 + cr * 12 + co * 6);
    uts_25C_MPa = Math.round(yieldStrength_25C_MPa * 1.32 + 80);
    elongation_pct = Math.max(6, Math.min(28, parseFloat((28 - gammaPrimeFormers * 1.6).toFixed(1))));
    youngsModulus_GPa = Math.round(205 + refractoryMoW * 3.5);

    crystalSystem = "FCC";
    spaceGroup = "Fm-3m (225)";
    latticeA_A = parseFloat((3.524 + cr * 0.0018 + mo * 0.0035 + w * 0.0038 + ta * 0.0045 + al * 0.0022 + ti * 0.003).toFixed(3));

    if (nb > 2.5) {
      targetPhases = ["austenite-fcc", "gamma-double-prime", "laves-fe2nb"];
      standardDesignation = "UNS N07718 / AMS 5662";
    } else if (gammaPrimeFormers > 3.0) {
      targetPhases = ["austenite-fcc", "gamma-prime-ni3al", "carbide-mc"];
      standardDesignation = "AMS 5873 (René 41 Class)";
    } else {
      targetPhases = ["austenite-fcc", "carbide-m23c6"];
      standardDesignation = "Hastelloy X Class";
    }

    thermalConductivity_k_WmK = parseFloat((11.0 + refractoryMoW * 0.3 - (cr + al) * 0.15).toFixed(1));
    specificHeat_Cp_JkgK = 435;
    recommendedLaserPower_W = 280;
    recommendedScanSpeed_mms = 940;

    const freezingRange = liquidus_C - solidus_C;
    if (freezingRange > 80 || (al + ti) > 4.5) {
      hotTearingSusceptibility = "High";
      crackingMechanism = "Strain-age cracking along high-angle grain boundaries (Al+Ti > 4.5 wt%)";
      mitigationRecommendation = "Elevate build plate preheating to >=200°C; implement rapid solidification scan vectors.";
    } else if (freezingRange > 45) {
      hotTearingSusceptibility = "Moderate";
      crackingMechanism = "Terminal liquid film tearing in interdendritic zones";
      mitigationRecommendation = "Apply 100-150°C preheat; use bidirectional island scanning pattern with 67° rotation.";
    } else {
      hotTearingSusceptibility = "Low";
      crackingMechanism = "Negligible hot tearing under standard parameter window";
      mitigationRecommendation = "Standard LPBF parameters: 280W, 950 mm/s, 110 µm hatch.";
    }
  } else if (baseMetal === "Ti") {
    category = "Titanium Alloy";
    standardDesignation = "ASTM B348 / AMS 4928";
    const alEquiv = al + (1 / 3) * (composition["Sn"] || 0) + (1 / 6) * (composition["Zr"] || 0);
    const moEquiv = mo + 0.67 * v + 0.44 * (composition["W"] || 0) + 0.28 * nb + 1.25 * cr + 1.25 * fe;

    liquidus_C = Math.round(1668 - (fe * 12 + cr * 8 + mo * 2 - alEquiv * 4));
    solidus_C = Math.round(liquidus_C - (40 + moEquiv * 8));
    solvus_C = Math.round(882 + alEquiv * 12.5 - moEquiv * 14.5);

    yieldStrength_25C_MPa = Math.round(450 + alEquiv * 68 + moEquiv * 42);
    uts_25C_MPa = Math.round(yieldStrength_25C_MPa * 1.15 + 60);
    elongation_pct = Math.max(8, Math.min(22, parseFloat((18 - (alEquiv + moEquiv) * 0.8).toFixed(1))));
    youngsModulus_GPa = Math.round(114 - moEquiv * 1.5);

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

    thermalConductivity_k_WmK = 6.7;
    specificHeat_Cp_JkgK = 526;
    recommendedLaserPower_W = 200;
    recommendedScanSpeed_mms = 1200;
    recommendedPreheatTemp_C = 200;
    hotTearingSusceptibility = "Low";
    crackingMechanism = "High residual stress accumulation due to low thermal conductivity";
    mitigationRecommendation = "Maintain argon inert atmosphere (<200 ppm O2) and heated build platform.";
  } else if (baseMetal === "Fe") {
    category = "Steels & Irons";
    // Si defaults to 0: a Si-free composition gave NaN here and skipped the austenitic branch below.
    const crEq = cr + mo * 1.5 + (composition["Si"] || 0) * 1.5 + (composition["Nb"] || 0) * 0.5;
    // Parenthesised: `Ni || 0 + ...` counted only Ni whenever Ni was present (C, N, Mn were dropped).
    const niEq = (composition["Ni"] || 0) + c * 30 + (composition["N"] || 0) * 30 + (composition["Mn"] || 0) * 0.5;

    liquidus_C = Math.round(1538 - (c * 65 + cr * 2.5 + niEq * 2));
    solidus_C = Math.round(liquidus_C - (30 + c * 80 + cr * 3));
    solvus_C = Math.round(727 + cr * 8 - niEq * 12);

    if (niEq > 8 && crEq > 16) {
      standardDesignation = "AISI 316L / ASTM A276";
      crystalSystem = "FCC";
      spaceGroup = "Fm-3m (225)";
      latticeA_A = 3.595;
      targetPhases = ["austenite-fcc", "delta-ferrite"];
      yieldStrength_25C_MPa = Math.round(480 + (cr - 16) * 15 + (mo - 2) * 25);
      uts_25C_MPa = Math.round(yieldStrength_25C_MPa * 1.35 + 100);
      elongation_pct = 38;
      youngsModulus_GPa = 195;
      thermalConductivity_k_WmK = 16.2;
    } else {
      standardDesignation = "Alloy Steel / Tool Steel";
      crystalSystem = "BCC";
      spaceGroup = "Im-3m (229)";
      latticeA_A = 2.866;
      targetPhases = ["martensite-bct", "retained-austenite"];
      yieldStrength_25C_MPa = Math.round(750 + c * 900 + cr * 25 + mo * 40);
      uts_25C_MPa = Math.round(yieldStrength_25C_MPa * 1.28 + 120);
      elongation_pct = 14;
      youngsModulus_GPa = 210;
      thermalConductivity_k_WmK = 24.5;
    }

    specificHeat_Cp_JkgK = 500;
    recommendedLaserPower_W = 220;
    recommendedScanSpeed_mms = 850;
    recommendedPreheatTemp_C = 100;
    hotTearingSusceptibility = "Low";
    crackingMechanism = "Thermal stress cracking during rapid martensitic transformation";
    mitigationRecommendation = "Stress relief anneal within 2 hours of post-build cooling.";
  } else if (baseMetal === "Al") {
    category = "Aluminum Alloys";
    standardDesignation = "AlSi10Mg / EN AC-43000";
    // Absent Cu counts as 0 wt% (a Cu-free alloy such as AlSi10Mg gave NaN).
    liquidus_C = Math.round(660 - (si * 6.5 + mg * 4.5 + (composition["Cu"] || 0) * 3));
    solidus_C = 570;
    solvus_C = 510;
    yieldStrength_25C_MPa = Math.round(240 + si * 8 + mg * 35);
    uts_25C_MPa = Math.round(yieldStrength_25C_MPa * 1.45);
    elongation_pct = 8.5;
    youngsModulus_GPa = 71;
    crystalSystem = "FCC";
    spaceGroup = "Fm-3m (225)";
    latticeA_A = 4.049;
    targetPhases = ["alpha-al-fcc", "eutectic-si", "mg2si-precipitates"];
    thermalConductivity_k_WmK = 140;
    specificHeat_Cp_JkgK = 900;
    recommendedLaserPower_W = 350;
    recommendedScanSpeed_mms = 1300;
    recommendedPreheatTemp_C = 150;
    hotTearingSusceptibility = "Moderate";
    crackingMechanism = "Gas porosity & keyholing from high optical reflectivity at 1064nm";
    mitigationRecommendation = "Utilize higher laser power (350W+), preheat bed to 150°C, and maintain strict powder dryness.";
  }

  // HV is never measured here. The old per-class rules (YS/3.05 Ni, YS/2.9 Ti, YS/3.1 steel, 210 HV austenitic,
  // 115 HV Al, 380 HV for every other base) had no source; see hardnessStrengthEstimate.ts.
  const hardnessEstimate = estimateSpecimenHardnessHV({
    baseMetal,
    crystalSystem,
    composition,
    yieldStrength_MPa: yieldStrength_25C_MPa,
  });

  const name = customName || existingMetadata?.name || `${chemicalFormula} Specimen`;

  const metadata: MaterialMetadata = {
    id: existingMetadata?.id || `specimen-${Date.now()}`,
    serialNumber: existingMetadata?.serialNumber || `SPEC-${baseMetal}-${Date.now().toString().slice(-4)}`,
    category,
    baseMetal,
    standardDesignation,
    manufacturingRoute: existingMetadata?.manufacturingRoute || "LPBF (Laser Powder Bed Fusion)",
    condition: existingMetadata?.condition || "As-Built / Condition T6",
    leadMetallurgist: existingMetadata?.leadMetallurgist || "Dr. E. Vance (Chief Metallurgist)",
    organization: existingMetadata?.organization || "MetalliX ICME Materials Consortium",
    notes: existingMetadata?.notes || `Universal Specimen Thread (${chemicalFormula})`,
    createdDate: existingMetadata?.createdDate || new Date().toISOString().split("T")[0],
    lastModified: Date.now(),
    source: existingMetadata?.source || "MetalliX Universal Material Store",
    density_gcm3,
    tags: existingMetadata?.tags || [category, baseMetal, "Universal Specimen"],
  };

  return {
    name,
    chemicalFormula,
    composition,
    unit: "wt_pct",
    metadata,
    liquidus_C,
    solidus_C,
    freezingRange_C: liquidus_C - solidus_C,
    solvus_C,
    stablePhases: targetPhases,
    yieldStrength_25C_MPa,
    uts_25C_MPa,
    youngsModulus_GPa,
    elongation_pct,
    hardness_HV: hardnessEstimate.hv,
    hardnessHVStatus: hardnessEstimate.status,
    hardnessHVNote: hardnessEstimate.note,
    lpbf: {
      recommendedLaserPower_W,
      recommendedScanSpeed_mms,
      recommendedHatch_um: 110,
      recommendedLayer_um: 30,
      recommendedPreheatTemp_C,
      thermalConductivity_k_WmK,
      density_rho_kgm3,
      specificHeat_Cp_JkgK,
      laserAbsorptivity: baseMetal === "Al" ? 0.32 : baseMetal === "Ti" ? 0.76 : 0.68,
      thermalExpansion_CTE_10e6: baseMetal === "Al" ? 23.5 : baseMetal === "Ti" ? 8.6 : 13.2,
      criticalGradient_G_Km: 4.8e5,
      hotTearingSusceptibility,
      crackingMechanism,
      mitigationRecommendation,
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

/** Persisted state before version 1 carries hardness_HV from the removed unsourced YS/x rules. */
export function migrateMaterialStoreState(persisted: unknown, version: number): unknown {
  if (version >= 1 || !persisted || typeof persisted !== "object") return persisted;
  const state = persisted as Record<string, unknown>;
  // Every specimen-like entry is recomputed; one without a yield strength gets Unavailable ("no yield strength" or the
  // class reason) instead of keeping its stale HV. Non-objects pass through.
  const fix = (s: unknown) =>
    isPersistableSpecimen(s) && ("hardness_HV" in s || "yieldStrength_25C_MPa" in s)
      ? withHardnessEstimate(s as MaterialSpecimen)
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
    name: "René 850 High-T Marine Superalloy",
    category: "Nickel Superalloy",
    base: "Ni",
    standard: "Aerospace High-T Turbine Rotor",
    description: "Gamma-prime strengthened superalloy engineered for marine turbine rotors operating at 850°C.",
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
        // Atomic-percent edits retain their unit and identity; weight-percent models are not evaluated.
        if (current.unit === "at_pct") {
          const next: MaterialSpecimen = withHardnessEstimate({...current,composition:resolvedComp,name:customName||current.name,sourceTab,lastModified:Date.now(),isCustomModified:true,metadata:{...current.metadata,...metadataPatch,source:"Atomic-percent composition; weight-percent property estimates unresolved"}});
          set({activeMaterialSpecimen:next,activeSpecimen:next});
          return;
        }
        const updatedMetadata = { ...current.metadata, ...metadataPatch, lastModified: Date.now() };
        const derived = deriveProperties(resolvedComp, customName || current.name, undefined, updatedMetadata);

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
              criticalTemp_Ac3_C: nextSpecimen.solvus_C + 50,
              solidusTemp_C: nextSpecimen.solidus_C,
              precipitateType: "Intermetallic / Carbides",
              initialPrecipVolFrac: 15,
              precipMeanRadius_nm: 25,
              hallPetch_ky_MPa_um05: 750,
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
              strengthCoefficient_K_MPa: nextSpecimen.uts_25C_MPa * 1.45,
              cahoon_m: 0.33,
              tabor_c: 2.95,
              taborConstraintFactor_c: 2.95,
              hollomon_alpha: 0.002,
              elasticModulus_E_GPa: nextSpecimen.youngsModulus_GPa,
              youngsModulus_E_GPa: nextSpecimen.youngsModulus_GPa,
              poissonsRatio_nu: 0.31,
              poissonsRatio: 0.31,
              uniformElongation_pct: nextSpecimen.elongation_pct,
              fractureToughness_K1c_MPa_sqrt_m: 65,
              estimatedK1c_MPam05: 65,
              anisotropyFactors: {
                L: { yieldFactor: 1.0, utsFactor: 1.0, elongFactor: 1.0, k1cFactor: 1.0 },
                LT: { yieldFactor: 0.94, utsFactor: 0.96, elongFactor: 0.88, k1cFactor: 0.91 },
                ST: { yieldFactor: 0.88, utsFactor: 0.91, elongFactor: 0.72, k1cFactor: 0.82 },
              },
              description: `Universal Specimen Thread (${nextSpecimen.chemicalFormula})`,
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
        const nextMetadata: MaterialMetadata = {
          ...current.metadata,
          ...metadataPatch,
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
      version: 1,
      migrate: (persisted, version) => migrateMaterialStoreState(persisted, version) as MaterialStore,
      merge: (persisted, current) => mergeMaterialStoreState(persisted, current),
    }
  )
);
