import { create } from "zustand";
import { persist } from "zustand/middleware";
import { materialProfileIdentity } from "../utils/materialProfileIdentity";
import { materialCategoryForBase } from "../utils/materialCategory";
import { setActivePipelineMaterial, PipelineMaterialPayload } from "../utils/materialDataPipeline";

export type BaseMetalType = "Ni" | "Fe" | "Ti" | "Al" | "Cu" | "Co" | "Mg" | "Refractory" | "Other";

export type LpbfScanStrategy = "island" | "meander-67" | "stripe";
export type LpbfBeamProfile = "gaussian" | "flat-top";

export interface LpbfSpecimenState {
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
  /** Active Build Job process vector — single source for all LPBF sub-labs */
  laserPower_W: number;
  scanSpeed_mms: number;
  hatch_um: number;
  layer_um: number;
  beamDiameter_um: number;
  preheatTemp_C: number;
  scanStrategy: LpbfScanStrategy;
  beamProfile: LpbfBeamProfile;
  cadAssetName: string;
  specimenDoi: string;
  /** Deterministic seed for Python screening extras (Marangoni pores, etc.). */
  processSeed: number;
  /** Surface incline from horizontal (deg); solidification R = v·cos(θ). */
  inclineAngle_deg: number;
  /** Overhang from vertical (deg); omit/0 = flat upskin. */
  downskinOverhang_deg: number;
}

export type LpbfProcessPatch = Partial<
  Pick<
    LpbfSpecimenState,
    | "laserPower_W"
    | "scanSpeed_mms"
    | "hatch_um"
    | "layer_um"
    | "beamDiameter_um"
    | "preheatTemp_C"
    | "scanStrategy"
    | "beamProfile"
    | "cadAssetName"
    | "specimenDoi"
    | "processSeed"
    | "inclineAngle_deg"
    | "downskinOverhang_deg"
  >
>;

export function withLpbfProcessDefaults(lpbf: Partial<LpbfSpecimenState> & Pick<LpbfSpecimenState, "recommendedLaserPower_W" | "recommendedScanSpeed_mms" | "recommendedHatch_um" | "recommendedLayer_um" | "recommendedPreheatTemp_C">): LpbfSpecimenState {
  return {
    recommendedLaserPower_W: lpbf.recommendedLaserPower_W,
    recommendedScanSpeed_mms: lpbf.recommendedScanSpeed_mms,
    recommendedHatch_um: lpbf.recommendedHatch_um,
    recommendedLayer_um: lpbf.recommendedLayer_um,
    recommendedPreheatTemp_C: lpbf.recommendedPreheatTemp_C,
    thermalConductivity_k_WmK: lpbf.thermalConductivity_k_WmK ?? 11.5,
    density_rho_kgm3: lpbf.density_rho_kgm3 ?? 8200,
    specificHeat_Cp_JkgK: lpbf.specificHeat_Cp_JkgK ?? 435,
    laserAbsorptivity: lpbf.laserAbsorptivity ?? 0.58,
    thermalExpansion_CTE_10e6: lpbf.thermalExpansion_CTE_10e6 ?? 13,
    criticalGradient_G_Km: lpbf.criticalGradient_G_Km ?? 1.5e7,
    hotTearingSusceptibility: lpbf.hotTearingSusceptibility ?? "Moderate",
    crackingMechanism: lpbf.crackingMechanism ?? "",
    mitigationRecommendation: lpbf.mitigationRecommendation ?? "",
    laserPower_W: lpbf.laserPower_W ?? lpbf.recommendedLaserPower_W,
    scanSpeed_mms: lpbf.scanSpeed_mms ?? lpbf.recommendedScanSpeed_mms,
    hatch_um: lpbf.hatch_um ?? lpbf.recommendedHatch_um,
    layer_um: lpbf.layer_um ?? lpbf.recommendedLayer_um,
    beamDiameter_um: lpbf.beamDiameter_um ?? 80,
    preheatTemp_C: lpbf.preheatTemp_C ?? lpbf.recommendedPreheatTemp_C,
    scanStrategy: lpbf.scanStrategy ?? "stripe",
    beamProfile: lpbf.beamProfile ?? "gaussian",
    cadAssetName: lpbf.cadAssetName ?? "",
    specimenDoi: lpbf.specimenDoi ?? "",
    processSeed: lpbf.processSeed ?? 42,
    inclineAngle_deg: lpbf.inclineAngle_deg ?? 0,
    downskinOverhang_deg: lpbf.downskinOverhang_deg ?? 0,
  };
}

export interface ActiveSpecimenState {
  id: string;
  name: string;
  chemicalFormula: string;
  category: string;
  baseMetal: BaseMetalType;
  composition: Record<string, number>; // element symbol -> wt%
  unit: "wt_pct" | "at_pct";
  
  // Thermodynamic Properties (Propagated directly to Tab 2 CALPHAD & Gibbs)
  liquidus_C: number;
  solidus_C: number;
  freezingRange_C: number;
  solvus_C: number;
  stablePhases: string[];
  
  // Mechanical Properties
  yieldStrength_25C_MPa: number;
  uts_25C_MPa: number;
  density_gcm3: number;
  youngsModulus_GPa: number;
  elongation_pct: number;
  
  // 3D LPBF Additive & Melt Pool Parameters (single Build Job source)
  lpbf: LpbfSpecimenState;
  
  // Crystallography & XRD (Propagated directly to XRD Lab)
  xrd: {
    crystalSystem: "FCC" | "BCC" | "HCP" | "Tetragonal" | "Other";
    spaceGroup: string;
    latticeA_A: number;
    latticeC_A?: number;
    targetPhases: string[];
    microstrain_pct: number;
    crystalliteSize_nm: number;
  };
  
  // Identity transfer never upgrades existing estimates to measured evidence.
  materialTransfer?: {sourceModule:string;sourceRecordId:string;compositionInterpretation:string;resultType:"Screening only";note:string};
  // Provenance & Digital Thread
  sourceTab: string;
  lastModified: number;
  isCustomModified: boolean;
}

export interface MaterialSpecimenStore {
  activeSpecimen: ActiveSpecimenState;
  
  // Actions
  updateComposition: (
    newComposition: Record<string, number>,
    customName?: string,
    forcedBaseMetal?: BaseMetalType,
    sourceTab?: string
  ) => void;
  setSpecimen: (specimen: Partial<ActiveSpecimenState>) => void;
  updateLpbfProcess: (patch: LpbfProcessPatch) => void;
  loadPreset: (presetId: string) => void;
  resetToDefault: () => void;
}

// ----------------------------------------------------------------------
// Physics Calculation Helpers
// ----------------------------------------------------------------------

export function detectBaseMetalFromComposition(comp: Record<string, number>): BaseMetalType {
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

// Element standard elemental densities (g/cm^3)
const ELEMENT_DENSITIES: Record<string, number> = {
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

// Compute rule-of-mixtures density
export function calculateAlloyDensity(comp: Record<string, number>): number {
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

// Generate chemical formula string from composition (e.g. Ni-16Cr-8.5Co-1.7Mo-2.6W-1.7Ta-3.4Al-3.4Ti)
export function generateChemicalFormula(comp: Record<string, number>, baseMetal: BaseMetalType): string {
  // Sort elements by percentage descending, with base metal first
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

// Compute comprehensive physical, thermodynamic & additive parameters from composition
export function deriveSpecimenProperties(
  composition: Record<string, number>,
  customName?: string,
  forcedBase?: BaseMetalType
): Omit<ActiveSpecimenState, "id" | "sourceTab" | "lastModified" | "isCustomModified"> {
  const baseMetal = forcedBase || detectBaseMetalFromComposition(composition);
  const density_gcm3 = calculateAlloyDensity(composition);
  const density_rho_kgm3 = Math.round(density_gcm3 * 1000);
  const chemicalFormula = generateChemicalFormula(composition, baseMetal);

  // Normalize / compute key additions
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
    // Nickel Superalloy Physics
    const gammaPrimeFormers = al + ti + ta + nb;
    const refractoryMoW = mo + w;

    liquidus_C = Math.round(1455 - (cr * 2.5 + mo * 4 + al * 8 + ti * 10 + c * 40));
    solidus_C = Math.round(liquidus_C - (35 + gammaPrimeFormers * 4.5 + nb * 12 + c * 30));
    solvus_C = Math.min(solidus_C - 40, Math.round(950 + gammaPrimeFormers * 22 + refractoryMoW * 6));

    // Yield strength model: solid solution (Mo, W, Co, Cr) + precipitation hardening (gamma prime Al, Ti, Ta)
    yieldStrength_25C_MPa = Math.round(320 + gammaPrimeFormers * 85 + refractoryMoW * 45 + cr * 12 + co * 6);
    uts_25C_MPa = Math.round(yieldStrength_25C_MPa * 1.32 + 80);
    elongation_pct = Math.max(6, Math.min(28, parseFloat((28 - gammaPrimeFormers * 1.6).toFixed(1))));
    youngsModulus_GPa = Math.round(205 + refractoryMoW * 3.5);

    crystalSystem = "FCC";
    spaceGroup = "Fm-3m (225)";
    // Solute expansion on lattice parameter
    latticeA_A = parseFloat((3.524 + cr * 0.0018 + mo * 0.0035 + w * 0.0038 + ta * 0.0045 + al * 0.0022 + ti * 0.003).toFixed(3));

    if (nb > 2.5) {
      targetPhases = ["austenite-fcc", "gamma-double-prime", "laves-fe2nb"];
    } else if (gammaPrimeFormers > 3.0) {
      targetPhases = ["austenite-fcc", "gamma-prime-ni3al", "carbide-mc"];
    } else {
      targetPhases = ["austenite-fcc", "carbide-m23c6"];
    }

    thermalConductivity_k_WmK = parseFloat((11.0 + refractoryMoW * 0.3 - (cr + al) * 0.15).toFixed(1));
    specificHeat_Cp_JkgK = 435;
    recommendedLaserPower_W = 280;
    recommendedScanSpeed_mms = 940;
    
    // Kou cracking index estimation
    const freezingRange = liquidus_C - solidus_C;
    if (freezingRange > 80 || (al + ti) > 4.5) {
      hotTearingSusceptibility = "High";
      recommendedPreheatTemp_C = 200;
      crackingMechanism = "Strain-age cracking and liquation cracking across high-angle grain boundaries (Al+Ti > 4.5%).";
      mitigationRecommendation = "Elevate build platform to 200–300°C; apply pulsed remelting or lower scan speed.";
    } else if (freezingRange > 45) {
      hotTearingSusceptibility = "Moderate";
      recommendedPreheatTemp_C = 100;
      crackingMechanism = "Interdendritic solute enrichment (Nb/Mo/Ti) forming low-melting terminal eutectics.";
      mitigationRecommendation = "Build plate preheat 100–150°C and meander scan rotation 67° to disperse thermal accumulation.";
    } else {
      hotTearingSusceptibility = "Low";
      recommendedPreheatTemp_C = 60;
      crackingMechanism = "Narrow solidification range limits liquid film rupture risk.";
      mitigationRecommendation = "Standard LPBF process window applicable.";
    }
  } else if (baseMetal === "Ti") {
    // Titanium Alloy Physics
    const alEquiv = al + (composition["Sn"] || 0) / 3 + (composition["Zr"] || 0) / 6 + 10 * (composition["O"] || 0.15);
    const moEquiv = mo + (composition["Ta"] || 0) / 5 + (composition["Nb"] || 0) / 3.6 + (composition["W"] || 0) / 2.5 + (composition["V"] || 0) / 1.5;

    liquidus_C = Math.round(1665 + al * 4 - moEquiv * 8);
    solidus_C = Math.round(liquidus_C - 55);
    solvus_C = Math.round(882 + alEquiv * 12.5 - moEquiv * 15); // Beta transus
    
    yieldStrength_25C_MPa = Math.round(820 + alEquiv * 40 + moEquiv * 35);
    uts_25C_MPa = Math.round(yieldStrength_25C_MPa + 90);
    elongation_pct = 14;
    youngsModulus_GPa = 114;

    crystalSystem = "HCP";
    spaceGroup = "P6_3/mmc (194)";
    latticeA_A = 2.950;
    latticeC_A = 4.686;
    targetPhases = ["ti-alpha-hcp", "ti-beta-bcc"];

    thermalConductivity_k_WmK = 6.7;
    specificHeat_Cp_JkgK = 526;
    recommendedLaserPower_W = 240;
    recommendedScanSpeed_mms = 1200;
    recommendedPreheatTemp_C = 150;
    hotTearingSusceptibility = "Moderate";
    crackingMechanism = "Ultra-low thermal conductivity causes localized thermal shock and brittle martensitic alpha' transformation.";
    mitigationRecommendation = "Use 150–200°C baseplate preheat and high-purity argon (O2 < 100 ppm).";
  } else if (baseMetal === "Fe") {
    // Steel / Stainless Steel Physics
    liquidus_C = Math.round(1538 - (cr * 3.5 + (composition["Ni"] || 0) * 4.5 + c * 75));
    solidus_C = Math.round(liquidus_C - (30 + c * 40));
    solvus_C = 727;
    
    yieldStrength_25C_MPa = Math.round(310 + cr * 14 + mo * 25 + (composition["Ni"] || 0) * 8 + c * 450);
    uts_25C_MPa = Math.round(yieldStrength_25C_MPa + 260);
    elongation_pct = 40;
    youngsModulus_GPa = 195;

    crystalSystem = cr > 12 && (composition["Ni"] || 0) > 8 ? "FCC" : "BCC";
    spaceGroup = crystalSystem === "FCC" ? "Fm-3m (225)" : "Im-3m (229)";
    latticeA_A = crystalSystem === "FCC" ? 3.590 : 2.866;
    targetPhases = crystalSystem === "FCC" ? ["austenite-fcc", "delta-ferrite"] : ["ferrite-bcc", "cementite-fe3c"];

    thermalConductivity_k_WmK = crystalSystem === "FCC" ? 15.2 : 28.0;
    specificHeat_Cp_JkgK = 500;
    recommendedLaserPower_W = 200;
    recommendedScanSpeed_mms = 850;
    recommendedPreheatTemp_C = 80;
    hotTearingSusceptibility = "Low";
    crackingMechanism = "Primary ferritic-austenitic solidification mode buffers thermal contraction.";
    mitigationRecommendation = "Standard build parameters with adequate support volume.";
  } else if (baseMetal === "Al") {
    // Aluminum Alloy Physics
    liquidus_C = 660 - (composition["Si"] || 0) * 7 - (composition["Mg"] || 0) * 5;
    solidus_C = liquidus_C - 45;
    solvus_C = 480;
    yieldStrength_25C_MPa = 280;
    uts_25C_MPa = 360;
    elongation_pct = 8;
    youngsModulus_GPa = 70;
    crystalSystem = "FCC";
    spaceGroup = "Fm-3m (225)";
    latticeA_A = 4.049;
    targetPhases = ["al-matrix-fcc", "mg2si-beta"];
    thermalConductivity_k_WmK = 130.0;
    specificHeat_Cp_JkgK = 910;
    recommendedLaserPower_W = 350;
    recommendedScanSpeed_mms = 1300;
    recommendedPreheatTemp_C = 160;
    hotTearingSusceptibility = "Moderate";
    crackingMechanism = "Wide freezing range and high thermal conductivity create rapid solidification contraction.";
    mitigationRecommendation = "High power laser (350W+) with 150°C preheat to mitigate keyhole porosity and lack-of-fusion.";
  }

  const freezingRange_C = Math.max(15, liquidus_C - solidus_C);

  // Auto-generate high-precision descriptive name if not provided
  const name = customName || `${baseMetal === "Ni" ? "Superalloy" : baseMetal} Specimen (${chemicalFormula})`;

  return {
    name,
    chemicalFormula,
    category: materialCategoryForBase(baseMetal),
    baseMetal,
    composition,
    unit: "wt_pct",
    liquidus_C,
    solidus_C,
    freezingRange_C,
    solvus_C,
    stablePhases: targetPhases,
    yieldStrength_25C_MPa,
    uts_25C_MPa,
    density_gcm3,
    youngsModulus_GPa,
    elongation_pct,
    lpbf: withLpbfProcessDefaults({
      recommendedLaserPower_W,
      recommendedScanSpeed_mms,
      recommendedHatch_um: 100,
      recommendedLayer_um: 40,
      recommendedPreheatTemp_C,
      thermalConductivity_k_WmK,
      density_rho_kgm3,
      specificHeat_Cp_JkgK,
      laserAbsorptivity: baseMetal === "Ti" ? 0.68 : baseMetal === "Al" ? 0.35 : 0.58,
      thermalExpansion_CTE_10e6: baseMetal === "Ni" ? 13.0 : baseMetal === "Ti" ? 8.6 : 16.5,
      criticalGradient_G_Km: 1.5e7,
      hotTearingSusceptibility,
      crackingMechanism,
      mitigationRecommendation,
    }),
    xrd: {
      crystalSystem,
      spaceGroup,
      latticeA_A,
      latticeC_A,
      targetPhases,
      microstrain_pct: 0.22,
      crystalliteSize_nm: 32,
    },
  };
}

// ----------------------------------------------------------------------
// Standard High-Performance Presets
// ----------------------------------------------------------------------

export const SPECIMEN_PRESETS: Record<string, { name: string; composition: Record<string, number>; base: BaseMetalType; description: string }> = {
  // Custom user superalloy from the critique prompt
  "custom-ni-superalloy": {
    name: "AeroTurbine-850 (Ni-16Cr-8.5Co-1.7Mo-2.6W-1.7Ta-3.4Al-3.4Ti)",
    base: "Ni",
    description: "Advanced gamma-prime precipitation hardened nickel superalloy optimized for 850°C marine turbine blades.",
    composition: {
      Ni: 62.7,
      Cr: 16.0,
      Co: 8.5,
      Al: 3.4,
      Ti: 3.4,
      W: 2.6,
      Mo: 1.7,
      Ta: 1.7,
    },
  },
  "inconel-718": {
    name: "Inconel 718 (AMS 5662 / UNS N07718)",
    base: "Ni",
    description: "Niobium-modified gamma-double-prime (Ni3Nb) superalloy with high weldability and tensile strength.",
    composition: {
      Ni: 52.5,
      Cr: 19.0,
      Fe: 18.5,
      Nb: 5.15,
      Mo: 3.05,
      Ti: 0.95,
      Al: 0.55,
      C: 0.04,
      Co: 0.35,
    },
  },
  "ti-6al-4v": {
    name: "Ti-6Al-4V Grade 23 ELI (ASTM F3001)",
    base: "Ti",
    description: "Lightweight, damage-tolerant alpha-beta titanium alloy with low interstitial oxygen for additive parts.",
    composition: {
      Ti: 89.2,
      Al: 6.2,
      V: 4.1,
      Fe: 0.25,
      O: 0.13,
      C: 0.05,
    },
  },
  "ss-316l": {
    name: "AISI 316L Stainless Steel (UNS S31603)",
    base: "Fe",
    description: "Molybdenum-bearing austenitic stainless steel with excellent corrosion resistance and ductile fracture.",
    composition: {
      Fe: 65.5,
      Cr: 17.5,
      Ni: 12.0,
      Mo: 2.5,
      Mn: 1.8,
      Si: 0.6,
      C: 0.02,
    },
  },
  "alsi10mg": {
    name: "AlSi10Mg Additive Lightweight",
    base: "Al",
    description: "Near-eutectic aluminum-silicon casting alloy with high thermal conductivity and rapid hardening kinetics.",
    composition: {
      Al: 89.5,
      Si: 9.8,
      Mg: 0.45,
      Fe: 0.20,
      Mn: 0.05,
    },
  },
};

// Keep the default within the LPBF material allowlist; experimental presets must be explicitly selected.
const INITIAL_SPECIMEN_PROPS = deriveSpecimenProperties(
  SPECIMEN_PRESETS["inconel-718"].composition,
  SPECIMEN_PRESETS["inconel-718"].name,
  SPECIMEN_PRESETS["inconel-718"].base
);

const INITIAL_SPECIMEN: ActiveSpecimenState = {
  id: "specimen-inconel-718",
  ...INITIAL_SPECIMEN_PROPS,
  sourceTab: "Alloy Formulator (Tab 1)",
  lastModified: Date.now(),
  isCustomModified: false,
};

// ----------------------------------------------------------------------
// Universal Zustand Reactive Store
// ----------------------------------------------------------------------

export const useMaterialSpecimenStore = create<MaterialSpecimenStore>()(
  persist(
    (set, get) => ({
      activeSpecimen: INITIAL_SPECIMEN,

      updateComposition: (newComposition, customName, forcedBaseMetal, sourceTab = "Alloy Formulator (Tab 1)") => {
        const previousProcess = get().activeSpecimen?.lpbf;
        const derived = deriveSpecimenProperties(newComposition, customName, forcedBaseMetal);
        const nextSpecimen: ActiveSpecimenState = {
          id: materialProfileIdentity(derived.name, derived.baseMetal, newComposition),
          ...derived,
          lpbf: withLpbfProcessDefaults({
            ...derived.lpbf,
            laserPower_W: previousProcess?.laserPower_W,
            scanSpeed_mms: previousProcess?.scanSpeed_mms,
            hatch_um: previousProcess?.hatch_um,
            layer_um: previousProcess?.layer_um,
            beamDiameter_um: previousProcess?.beamDiameter_um,
            preheatTemp_C: previousProcess?.preheatTemp_C,
            scanStrategy: previousProcess?.scanStrategy,
            beamProfile: previousProcess?.beamProfile,
            cadAssetName: previousProcess?.cadAssetName,
            specimenDoi: previousProcess?.specimenDoi,
          }),
          sourceTab,
          lastModified: Date.now(),
          isCustomModified: true,
        };

        set({ activeSpecimen: nextSpecimen });

        // Bridge to pipeline for modules that also listen to data pipeline
        try {
          const pipelinePayload: PipelineMaterialPayload = {
            id: nextSpecimen.id,
            name: nextSpecimen.name,
            category: nextSpecimen.category,
            standard: "MetalliX Universal Specimen Thread",
            sourceModule: sourceTab,
            timestamp: Date.now(),
            composition: nextSpecimen.composition,
            compositionUnit: nextSpecimen.unit,
            compositionInterpretation: "nominal",
            baseMetal: nextSpecimen.baseMetal as any,
            yieldStrength: nextSpecimen.yieldStrength_25C_MPa,
            tensileStrength: nextSpecimen.uts_25C_MPa,
            youngsModulus: nextSpecimen.youngsModulus_GPa,
            density: nextSpecimen.density_gcm3,
            elongation: nextSpecimen.elongation_pct,
            hardness: `${Math.round(nextSpecimen.yieldStrength_25C_MPa / 3.1)} HV`,
            hardnessHV: Math.round(nextSpecimen.yieldStrength_25C_MPa / 3.1),
            poissonsRatio: 0.31,
            thermalConductivity: nextSpecimen.lpbf.thermalConductivity_k_WmK,
            kineticProfile: {
              id: nextSpecimen.id,
              name: nextSpecimen.name,
              baseMetal: (["Ni", "Fe", "Ti", "Al"].includes(nextSpecimen.baseMetal) ? nextSpecimen.baseMetal : "Ni") as any,
              standardRef: "Universal Digital Specimen",
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
              category: (["Nickel Superalloy", "Titanium Alloy", "Aluminum Alloys", "Steels & Irons", "Cobalt / Bio"].includes(nextSpecimen.category)
                ? nextSpecimen.category
                : "Nickel Superalloy") as any,
              crystalStructure: nextSpecimen.xrd.crystalSystem as any,
              defaultHardnessHV: Math.round(nextSpecimen.yieldStrength_25C_MPa / 3.1),
              hardnessHV: Math.round(nextSpecimen.yieldStrength_25C_MPa / 3.1),
              measuredYield_MPa: nextSpecimen.yieldStrength_25C_MPa,
              measuredUTS_MPa: nextSpecimen.uts_25C_MPa,
              strainHardeningExponent_n: 0.15,
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
              standardRef: "ASTM E8 / E384 Universal Thread",
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
          console.warn("[MaterialSpecimenStore] Pipeline sync skipped:", e);
        }
      },

      setSpecimen: (partial) => {
        set((state) => ({
          activeSpecimen: {
            ...state.activeSpecimen,
            ...partial,
            lpbf: partial.lpbf
              ? withLpbfProcessDefaults({ ...state.activeSpecimen.lpbf, ...partial.lpbf })
              : state.activeSpecimen.lpbf,
            lastModified: Date.now(),
            isCustomModified: true,
          },
        }));
      },

      updateLpbfProcess: (patch) => {
        set((state) => ({
          activeSpecimen: {
            ...state.activeSpecimen,
            lpbf: withLpbfProcessDefaults({ ...state.activeSpecimen.lpbf, ...patch }),
            lastModified: Date.now(),
            isCustomModified: true,
          },
        }));
      },

      loadPreset: (presetId) => {
        const preset = SPECIMEN_PRESETS[presetId];
        if (!preset) return;
        get().updateComposition(preset.composition, preset.name, preset.base, `Preset (${preset.name})`);
        const rec = get().activeSpecimen.lpbf;
        get().updateLpbfProcess({
          laserPower_W: rec.recommendedLaserPower_W,
          scanSpeed_mms: rec.recommendedScanSpeed_mms,
          hatch_um: rec.recommendedHatch_um,
          layer_um: rec.recommendedLayer_um,
          preheatTemp_C: rec.recommendedPreheatTemp_C,
        });
      },

      resetToDefault: () => {
        set({ activeSpecimen: INITIAL_SPECIMEN });
      },
    }),
    {
      name: "metallix_active_material_specimen_v2",
      version: 2,
      partialize: (state) => ({ activeSpecimen: state.activeSpecimen }),
      merge: (persisted, current) => {
        const persistedState = persisted as Partial<MaterialSpecimenStore> | undefined;
        const specimen = persistedState?.activeSpecimen;
        if (!specimen) return current;
        return {
          ...current,
          ...persistedState,
          activeSpecimen: {
            ...current.activeSpecimen,
            ...specimen,
            lpbf: withLpbfProcessDefaults({
              ...current.activeSpecimen.lpbf,
              ...specimen.lpbf,
            }),
          },
        };
      },
    }
  )
);
