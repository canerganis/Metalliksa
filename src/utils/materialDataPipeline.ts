import { MaterialSpec } from "../types";
import { MaterialThermalProfile, ThermalStage, HardnessAlloyPreset } from "../types/thermalKinetic";
import { convertSteelHardness, hardnessMaterialClassOf } from "./hardnessConversion";
import { estimateSteelHvFromYield, HV_FROM_YIELD_ESTIMATE_NOTE } from "./hardnessStrengthEstimate";

export type ModuleTargetId =
  | "alloy-builder"
  | "phase-diagram"
  | "database"
  | "3d-distortion-lab";

export interface PipelineXRDPeak {
  twoTheta: number;
  intensity: number;
  hkl: string;
  phase: string;
  fwhm: number;
}

export interface PipelineMaterialPayload {
  id: string;
  name: string;
  category: string;
  standard: string;
  sourceModule: string;
  timestamp: number;
  composition: Record<string, number>;
  compositionUnit?: "wt_pct" | "at_pct";
  compositionInterpretation?: "nominal" | "range-midpoint";
  originalComposition?: Record<string, number | { min: number; max: number }>;
  baseMetal: "Ni" | "Fe" | "Ti" | "Al" | "Cu" | "Co" | "Mg" | "Other";
  
  // Mechanical & Physical Properties. null = unavailable: the shared specimen stores publish null here because they
  // have no validated composition-to-property model (catalogue records carry their tabulated values).
  yieldStrength: number | null;
  tensileStrength: number | null;
  youngsModulus: number | null;
  density: number;
  elongation: number | null;
  hardness: string;
  /** null = unavailable (no reported/convertible hardness and no verified relation for this alloy class). */
  hardnessHV: number | null;
  /** Where hardnessHV comes from: the hardness string, an ASTM E140 conversion of a reported hardness, or an estimate. */
  hardnessHVSource?: HardnessHVSource;
  hardnessHRC?: number;
  poissonsRatio: number;
  thermalConductivity?: number;
  microstructure?: string;
  
  // Calibrated Kinetic Profile (for Thermal Cycle Scheduler & Grain Growth)
  kineticProfile: MaterialThermalProfile;
  suggestedThermalCycle?: ThermalStage[];
  
  // Mechanical Hardness Profile (for Hardness-to-Tensile Lab)
  hardnessProfile: HardnessAlloyPreset;
  
  // Diffraction Profile (for XRD Lab)
  xrdProfile: {
    crystalSystem: string;
    spaceGroup: string;
    latticeA_A: number;
    latticeC_A?: number;
    primaryPhases: string[];
    peaks: PipelineXRDPeak[];
  };

  // Phase Diagram & ICME Parameters
  icmeProfile: {
    /** null = unavailable (not computed from composition). */
    liquidusTemp_C: number | null;
    solidusTemp_C: number | null;
    carbonEquivalent?: number;
    criticalAc3_C?: number;
    solvusTemp_C: number | null;
    dominantPhases: string[];
  };
}

const STORAGE_KEY = "metallix_active_pipeline_material";
const EVENT_NAME = "metallix-pipeline-updated";
const NAV_EVENT_NAME = "metallix-navigate-tab";

// Helper to extract numerical composition value
export function normalizeComposition(comp: Record<string, number | { min: number; max: number }>): Record<string, number> {
  const result: Record<string, number> = {};
  for (const [key, val] of Object.entries(comp)) {
    if (typeof val === "number") {
      result[key] = val;
    } else if (val && typeof val === "object") {
      const min = (val as any).min ?? 0;
      const max = (val as any).max ?? min;
      result[key] = parseFloat(((min + max) / 2).toFixed(3));
    }
  }
  return result;
}

// Detect base metal from category and composition
export function detectBaseMetal(category: string, comp: Record<string, number>): "Ni" | "Fe" | "Ti" | "Al" | "Cu" | "Co" | "Mg" | "Other" {
  const cat = category.toLowerCase();
  if (cat.includes("nickel") || cat.includes("superalloy") || (comp.Ni && comp.Ni > 40)) return "Ni";
  if (cat.includes("titanium") || (comp.Ti && comp.Ti > 50)) return "Ti";
  if (cat.includes("aluminum") || (comp.Al && comp.Al > 60)) return "Al";
  if (cat.includes("copper") || cat.includes("bronze") || cat.includes("brass") || (comp.Cu && comp.Cu > 50)) return "Cu";
  if (cat.includes("magnesium") || (comp.Mg && comp.Mg > 60)) return "Mg";
  if (cat.includes("cobalt") || (comp.Co && comp.Co > 40)) return "Co";
  if (cat.includes("steel") || cat.includes("iron") || (comp.Fe && comp.Fe > 40)) return "Fe";

  // Fallback: check highest element
  let maxElem = "Fe";
  let maxVal = -1;
  for (const [k, v] of Object.entries(comp)) {
    if (v > maxVal) {
      maxVal = v;
      maxElem = k;
    }
  }
  if (["Ni", "Fe", "Ti", "Al", "Cu", "Co", "Mg"].includes(maxElem)) {
    return maxElem as any;
  }
  return "Fe";
}

// Estimate ASTM Grain Growth / Heat Treatment Kinetics based on metallurgical principles
export function deriveKineticProfile(
  matName: string,
  baseMetal: "Ni" | "Fe" | "Ti" | "Al" | "Cu" | "Co" | "Mg" | "Other",
  comp: Record<string, number>,
  yieldStrength: number
): { profile: MaterialThermalProfile; stages: ThermalStage[]; icme: PipelineMaterialPayload["icmeProfile"] } {
  const C = comp.C || 0;
  const Cr = comp.Cr || 0;
  const Ni = comp.Ni || 0;
  const Mo = comp.Mo || 0;
  const Al = comp.Al || 0;
  const Ti = comp.Ti || 0;
  const Nb = comp.Nb || 0;
  const V = comp.V || 0;
  const Si = comp.Si || 0;
  const Mn = comp.Mn || 0;

  // Carbon Equivalent (IIW Formula)
  const CE = C + Mn / 6 + (Cr + Mo + V) / 5 + (Ni + (comp.Cu || 0)) / 15;

  let solvusTemp = 950;
  let ac3Temp = 900;
  let solidusTemp = 1350;
  let liquidusTemp = 1450;
  let Q_kJ = 270;
  let n_exp = 2.5;
  let k0 = 5e10;
  let initialGrain = 20.0;
  let precipType = "Dispersoids & Carbides";
  let precipVol = 3.0;
  let precipRadius = 40;
  let ky = 600;
  let frictionStress = Math.max(150, Math.round(yieldStrength * 0.45));

  let stages: ThermalStage[] = [];

  if (baseMetal === "Ni") {
    solvusTemp = Math.round(980 + Nb * 14 + Ti * 12 + Al * 8);
    ac3Temp = solvusTemp;
    solidusTemp = Math.max(1240, Math.round(1350 - Cr * 3 - Mo * 4));
    liquidusTemp = solidusTemp + 70;
    Q_kJ = 285;
    n_exp = 2.8;
    k0 = 8.5e10;
    initialGrain = 18.0;
    precipType = "γ' / γ'' Coherent Superlattice & MC Carbides";
    precipVol = Math.min(65, Math.max(4, Math.round((Al + Ti + Nb) * 3.5)));
    precipRadius = 35;
    ky = 750;
    frictionStress = Math.round(yieldStrength * 0.5);

    stages = [
      {
        id: "s1",
        name: "Controlled Vacuum Ramp",
        type: "ramp",
        startTempC: 25,
        targetTempC: Math.min(solidusTemp - 50, solvusTemp + 15),
        rate_C_per_min: 15,
        durationMinutes: Math.round((solvusTemp - 10) / 15),
        atmosphere: "Vacuum",
        purpose: "Preheat & dissolution of secondary phases",
      },
      {
        id: "s2",
        name: "Solution Anneal Soak",
        type: "soak",
        startTempC: Math.min(solidusTemp - 50, solvusTemp + 15),
        targetTempC: Math.min(solidusTemp - 50, solvusTemp + 15),
        durationMinutes: 60,
        atmosphere: "Vacuum",
        purpose: "Recrystallize matrix and dissolve precipitates",
      },
      {
        id: "s3",
        name: "Argon Gas Fan Quench",
        type: "quench",
        startTempC: Math.min(solidusTemp - 50, solvusTemp + 15),
        targetTempC: 720,
        rate_C_per_min: 80,
        durationMinutes: 4,
        atmosphere: "Argon",
        purpose: "Freeze supersaturated solid solution",
      },
      {
        id: "s4",
        name: "Primary Aging Precipitation Hold",
        type: "soak",
        startTempC: 720,
        targetTempC: 720,
        durationMinutes: 480,
        atmosphere: "Vacuum",
        purpose: "Dense nucleation of strengthening precipitates",
      },
      {
        id: "s5",
        name: "Final Controlled Cool",
        type: "quench",
        startTempC: 720,
        targetTempC: 25,
        rate_C_per_min: 25,
        durationMinutes: 28,
        atmosphere: "Air",
        purpose: "Room temperature discharge",
      },
    ];
  } else if (baseMetal === "Ti") {
    // Standard Beta-Transus Equation
    solvusTemp = Math.round(882 + 21.1 * Al - 9.5 * Mo - 6.9 * V - 11.8 * Cr - 12.1 * (comp.Fe || 0) + 4.2 * (comp.Sn || 0) + 1.7 * (comp.Zr || 0));
    solvusTemp = Math.min(1060, Math.max(850, solvusTemp));
    ac3Temp = solvusTemp;
    solidusTemp = 1604;
    liquidusTemp = 1660;
    Q_kJ = 250;
    n_exp = 2.5;
    k0 = 4.2e9;
    initialGrain = 12.0;
    precipType = "Primary α-Globules & Transformed β Lamellae";
    precipVol = 14.0;
    precipRadius = 90;
    ky = 820;
    frictionStress = Math.round(yieldStrength * 0.42);

    stages = [
      {
        id: "s1",
        name: "Sub-Transus Ramp",
        type: "ramp",
        startTempC: 25,
        targetTempC: solvusTemp - 40,
        rate_C_per_min: 12,
        durationMinutes: Math.round((solvusTemp - 65) / 12),
        atmosphere: "Vacuum",
        purpose: "Controlled preheat below beta transus",
      },
      {
        id: "s2",
        name: "Sub-Transus Solution Hold",
        type: "soak",
        startTempC: solvusTemp - 40,
        targetTempC: solvusTemp - 40,
        durationMinutes: 90,
        atmosphere: "Vacuum",
        purpose: "Partition alpha/beta volume fractions",
      },
      {
        id: "s3",
        name: "Forced Gas Quench",
        type: "quench",
        startTempC: solvusTemp - 40,
        targetTempC: 540,
        rate_C_per_min: 100,
        durationMinutes: 4,
        atmosphere: "Argon",
        purpose: "Transform retained beta to acicular alpha prime",
      },
      {
        id: "s4",
        name: "Stabilization & Stress Relief Hold",
        type: "soak",
        startTempC: 540,
        targetTempC: 540,
        durationMinutes: 240,
        atmosphere: "Vacuum",
        purpose: "Stabilize transformed microstructure",
      },
    ];
  } else if (baseMetal === "Al") {
    solvusTemp = Math.min(540, Math.max(460, Math.round(480 + (comp.Zn || 0) * 8 + (comp.Mg || 0) * 12 + Si * 5)));
    ac3Temp = solvusTemp;
    solidusTemp = Math.min(620, Math.max(475, Math.round(590 - (comp.Zn || 0) * 12 - (comp.Mg || 0) * 8 - (comp.Cu || 0) * 10)));
    liquidusTemp = solidusTemp + 65;
    Q_kJ = 140;
    n_exp = 2.1;
    k0 = 7.5e8;
    initialGrain = 10.0;
    precipType = "η'-MgZn2 / β''-Mg2Si / θ'-Al2Cu Nanoclusters";
    precipVol = 7.0;
    precipRadius = 12;
    ky = 230;
    frictionStress = Math.round(yieldStrength * 0.35);

    stages = [
      {
        id: "s1",
        name: "Solution Heat Treatment Ramp",
        type: "ramp",
        startTempC: 25,
        targetTempC: Math.min(solidusTemp - 15, solvusTemp),
        rate_C_per_min: 10,
        durationMinutes: 48,
        atmosphere: "Air",
        purpose: "Ramp safely below solidus",
      },
      {
        id: "s2",
        name: "Solution Soak",
        type: "soak",
        startTempC: Math.min(solidusTemp - 15, solvusTemp),
        targetTempC: Math.min(solidusTemp - 15, solvusTemp),
        durationMinutes: 60,
        atmosphere: "Air",
        purpose: "Complete solute dissolution into alpha-Al matrix",
      },
      {
        id: "s3",
        name: "Water Quench (20°C)",
        type: "quench",
        startTempC: Math.min(solidusTemp - 15, solvusTemp),
        targetTempC: 25,
        rate_C_per_min: 400,
        durationMinutes: 1.2,
        atmosphere: "Air",
        purpose: "Freeze supersaturated solid solution (SSSS)",
      },
      {
        id: "s4",
        name: "Artificial Aging (T6 Peak)",
        type: "soak",
        startTempC: 160,
        targetTempC: 160,
        durationMinutes: 720,
        atmosphere: "Air",
        purpose: "Precipitate fine coherent GP zones and hardening phases",
      },
    ];
  } else {
    // Steels / Fe-base: Andrews equation for Ac3
    ac3Temp = Math.round(910 - 203 * Math.sqrt(Math.max(0.01, C)) - 15.2 * Ni + 44.7 * Si + 104 * V + 31.5 * Mo + 13.1 * (comp.W || 0));
    ac3Temp = Math.min(1050, Math.max(740, ac3Temp));
    solvusTemp = ac3Temp;
    solidusTemp = Math.round(1538 - 88 * C - 8 * Si - 5 * Mn - 1.5 * Cr - 4 * Ni);
    liquidusTemp = solidusTemp + 55;
    Q_kJ = 260;
    n_exp = 2.4;
    k0 = 5e10;
    initialGrain = 22.0;
    precipType = "Alloy Carbides (M23C6, MC, Cementite)";
    precipVol = Math.min(12, Math.max(1.5, Math.round(C * 14 + (Cr + Mo + V) * 0.5)));
    precipRadius = 45;
    ky = 550;
    frictionStress = Math.round(yieldStrength * 0.4);

    stages = [
      {
        id: "s1",
        name: "Austenitizing Ramp",
        type: "ramp",
        startTempC: 25,
        targetTempC: ac3Temp + 45,
        rate_C_per_min: 15,
        durationMinutes: Math.round((ac3Temp + 20) / 15),
        atmosphere: "Nitrogen",
        purpose: "Transform to homogeneous single-phase austenite (γ)",
      },
      {
        id: "s2",
        name: "Austenitizing Soak",
        type: "soak",
        startTempC: ac3Temp + 45,
        targetTempC: ac3Temp + 45,
        durationMinutes: 45,
        atmosphere: "Nitrogen",
        purpose: "Full carbon dissolution and austenitization",
      },
      {
        id: "s3",
        name: "Oil / Polymer Quench",
        type: "quench",
        startTempC: ac3Temp + 45,
        targetTempC: 50,
        rate_C_per_min: 250,
        durationMinutes: 3.5,
        atmosphere: "Air",
        purpose: "Suppress ferrite/pearlite; transform to hard martensite (α')",
      },
      {
        id: "s4",
        name: "Tempering Hold",
        type: "soak",
        startTempC: 480,
        targetTempC: 480,
        durationMinutes: 120,
        atmosphere: "Air",
        purpose: "Precipitate fine carbides, relieve stress, recover ductility",
      },
    ];
  }

  const profile: MaterialThermalProfile = {
    id: matName.toLowerCase().replace(/[^a-z0-9]/g, "_"),
    name: matName,
    baseMetal: ["Ni", "Fe", "Ti", "Al"].includes(baseMetal) ? (baseMetal as any) : "Fe",
    standardRef: "ASTM / AMS Engineering Material Specification",
    initialGrainSize_um: initialGrain,
    grainGrowthExponent_n: n_exp,
    activationEnergy_kJ_mol: Q_kJ,
    preExponential_k0: k0,
    solvusTemp_C: solvusTemp,
    criticalTemp_Ac3_C: ac3Temp,
    solidusTemp_C: solidusTemp,
    precipitateType: precipType,
    initialPrecipVolFrac: precipVol,
    precipMeanRadius_nm: precipRadius,
    hallPetch_ky_MPa_um05: ky,
    baseFrictionStress_MPa: frictionStress,
  };

  const icme = {
    liquidusTemp_C: liquidusTemp,
    solidusTemp_C: solidusTemp,
    carbonEquivalent: parseFloat(CE.toFixed(3)),
    criticalAc3_C: ac3Temp,
    solvusTemp_C: solvusTemp,
    dominantPhases: [baseMetal === "Ni" ? "FCC Matrix (γ)" : baseMetal === "Ti" ? "HCP Matrix (α)" : baseMetal === "Al" ? "FCC Matrix (α)" : "BCC/BCT Matrix (α)", precipType],
  };

  return { profile, stages, icme };
}

export type HardnessHVSource = "reported" | "converted-astm-e140" | "estimate-from-yield" | "estimate-predicted" | "unavailable";

/**
 * Display text of a payload HV with its basis: estimates and conversions are never shown as plain measured values.
 * When HV is unavailable but the record carries a reported hardness (e.g. "40 - 45 HRC"), that value is shown.
 */
export function pipelineHardnessText(
  hv: number | null | undefined,
  source: HardnessHVSource | undefined,
  reportedHardness?: string
): string {
  if (hv === null || hv === undefined) {
    const reported = reportedHardness?.trim();
    // Our own generated strings ("Unavailable: ...", "≈ n HV: estimate ...") are not reported values.
    return reported && !/^(unavailable|≈)/i.test(reported) ? `HV unavailable (reported: ${reported})` : "HV unavailable";
  }
  if (source === "converted-astm-e140") return `${hv} HV (converted, ASTM E140)`;
  if (source === "estimate-from-yield" || source === "estimate-predicted") return `${hv} HV (estimate, not measured)`;
  if (source === "reported") return `${hv} HV (reported)`;
  return `${hv} HV`;
}

/**
 * HRC <-> HV conversion only applies to non-austenitic steels (ASTM E140 Table 1). An Fe-base material whose name,
 * category or microstructure mentions austenite (austenitic or duplex stainless) is not converted.
 */
export function isNonAusteniticSteel(baseMetal: string, ...descriptors: Array<string | undefined>): boolean {
  return baseMetal === "Fe" && !descriptors.some((d) => d !== undefined && /austenit/i.test(d));
}

// Generate Hardness Preset & Mechanical Constitutive Parameters
export function deriveHardnessProfile(
  matName: string,
  category: string,
  baseMetal: string,
  yieldStrength: number,
  tensileStrength: number,
  youngsModulus: number,
  elongation: number,
  hardnessStr: string,
  microstructure?: string,
  /** true when hardnessStr itself is a prediction (e.g. a synthesized candidate), not a reported value */
  hardnessStrIsEstimate = false,
  /** wt% composition; the steel yield-strength relation needs a hypoeutectoid carbon or low-alloy steel */
  composition?: Record<string, number>
): { hardnessProfile: HardnessAlloyPreset; hardnessHV: number | null; hardnessHVSource: HardnessHVSource; hardnessHRC?: number } {
  let hv: number | null = null;
  let hvSource: HardnessHVSource = "unavailable";
  let hrc: number | undefined = undefined;
  let convertedFrom = "";
  let fromPredictedYield = false;
  let unavailableText = "HV unavailable";
  const steel = isNonAusteniticSteel(baseMetal, matName, category, microstructure);

  // Try extracting from hardness string. Scale <-> HV uses the ASTM E140 table interpolation, steels only.
  const hrcMatch = hardnessStr.match(/(\d+(\.\d+)?)\s*HRC/i);
  const hvMatch = hardnessStr.match(/(\d+(\.\d+)?)\s*HV/i);
  if (hrcMatch) {
    hrc = parseFloat(hrcMatch[1]);
    const convertedHV = steel ? convertSteelHardness(hrc, "HRC").HV : null;
    if (convertedHV !== null) {
      hv = convertedHV;
      hvSource = "converted-astm-e140";
      convertedFrom = `${hrc} HRC per ASTM E140 Table 1`;
    }
  } else if (hvMatch) {
    hv = parseFloat(hvMatch[1]);
    hvSource = hardnessStrIsEstimate ? "estimate-predicted" : "reported";
    if (steel) hrc = convertSteelHardness(hv, "HV").HRC ?? undefined;
  } else if (steel) {
    // Reported Rockwell B (E140 Table 2) or Brinell HBW (E140 Table 1, carbide ball): first one inside its table range.
    for (const [scale, table] of [["HRB", "Table 2"], ["HBW", "Table 1"]] as const) {
      const m = hardnessStr.match(new RegExp(`(\\d+(\\.\\d+)?)\\s*${scale}`, "i"));
      if (!m) continue;
      const value = parseFloat(m[1]);
      const conv = convertSteelHardness(value, scale);
      if (conv.HV !== null) {
        hv = conv.HV;
        hrc = conv.HRC ?? undefined;
        hvSource = "converted-astm-e140";
        convertedFrom = `${value} ${scale} per ASTM E140 ${table}`;
        break;
      }
    }
  }
  if (hv === null) {
    // No usable hardness: the steel-only yield-strength regression (Pavlina & Van Tyne 2008), else unavailable. The
    // old fallback HV ~ YS/3 + 35 (YS/3 + 30 for candidates) had no source.
    const est = estimateSteelHvFromYield(yieldStrength, {
      materialClass: steel ? "non-austenitic-steel" : hardnessMaterialClassOf({ baseMetal, crystalSystem: baseMetal === "Fe" ? "FCC" : undefined }),
      composition,
    });
    if (est.hv !== null) {
      hv = est.hv;
      hvSource = hardnessStrIsEstimate ? "estimate-predicted" : "estimate-from-yield";
      fromPredictedYield = hardnessStrIsEstimate;
    } else {
      unavailableText = est.note.replace(/^Unavailable: /, "HV unavailable: ");
    }
  }
  const hvSourceText: Record<HardnessHVSource, string> = {
    reported: `HV ${hv} as reported`,
    "converted-astm-e140": `HV ${hv} converted from ${convertedFrom} (approximate)`,
    "estimate-from-yield": `HV ${hv} is an ${HV_FROM_YIELD_ESTIMATE_NOTE}`,
    "estimate-predicted": fromPredictedYield
      ? `HV ${hv} is a predicted value from a predicted yield strength, not a measurement (${HV_FROM_YIELD_ESTIMATE_NOTE})`
      : `HV ${hv} is a predicted value, not a measurement`,
    unavailable: unavailableText,
  };

  const n_hollomon = Math.min(0.28, Math.max(0.08, parseFloat((0.45 * Math.pow(elongation / 100, 0.5)).toFixed(3))));
  const K_hollomon = Math.round(tensileStrength * Math.pow(Math.E / n_hollomon, n_hollomon));
  const tabor_c = baseMetal === "Al" ? 2.8 : baseMetal === "Ti" ? 3.1 : 3.0;
  const cahoon_m = baseMetal === "Al" ? 0.22 : 0.25;
  const k1c = Math.round(Math.max(30, 220 - (yieldStrength / 10) * 0.85));

  const hardnessProfile = {
    id: matName.toLowerCase().replace(/[^a-z0-9]/g, "_"),
    name: matName,
    category:
      category.includes("Nickel") || baseMetal === "Ni"
        ? "Nickel Superalloy"
        : category.includes("Titanium") || baseMetal === "Ti"
        ? "Titanium Alloy"
        : category.includes("Aluminum") || baseMetal === "Al"
        ? "Aluminum Alloys"
        : "Steels & Irons",
    defaultHardnessHV: hv ?? undefined,
    defaultHardnessHRC: hrc,
    taborConstraintFactor_c: tabor_c,
    cahoon_m: cahoon_m,
    elasticModulus_E_GPa: youngsModulus,
    poissonsRatio_nu: baseMetal === "Al" ? 0.33 : baseMetal === "Ti" ? 0.34 : 0.29,
    workHardeningExponent_n: n_hollomon,
    strengthCoefficient_K_MPa: K_hollomon,
    uniformElongation_pct: Math.round(elongation * 0.75),
    fractureToughness_K1c_MPa_sqrt_m: k1c,
    anisotropyFactors: {
      L: { yieldFactor: 1.0, utsFactor: 1.0, elongFactor: 1.0, k1cFactor: 1.0 },
      LT: { yieldFactor: 0.96, utsFactor: 0.97, elongFactor: 0.88, k1cFactor: 0.91 },
      ST: { yieldFactor: 0.91, utsFactor: 0.93, elongFactor: 0.72, k1cFactor: 0.82 },
    },
    description: hardnessStr && !hardnessStrIsEstimate
      ? `Calibrated from ${matName} with reported hardness ${hardnessStr}; ${hvSourceText[hvSource]}.`
      : `Calibrated from ${matName}; ${hvSourceText[hvSource]}.`,
  };

  return { hardnessProfile: hardnessProfile as any, hardnessHV: hv, hardnessHVSource: hvSource, hardnessHRC: hrc };
}

// Generate XRD Profile with characteristic Bragg Peaks (Cu-Kα = 1.5406 Å)
export function deriveXRDProfile(
  matName: string,
  baseMetal: string,
  comp: Record<string, number>
): PipelineMaterialPayload["xrdProfile"] {
  let crystalSystem = "Cubic (FCC)";
  let spaceGroup = "Fm-3m (225)";
  let latticeA = 3.59;
  let latticeC: number | undefined = undefined;
  let primaryPhases = ["γ-Matrix (FCC)"];
  let peaks: PipelineXRDPeak[] = [];

  if (baseMetal === "Ni") {
    crystalSystem = "Cubic (FCC)";
    spaceGroup = "Fm-3m (225)";
    latticeA = 3.595;
    primaryPhases = ["γ-Matrix (FCC)", "γ''-Ni3Nb (BCT)", "γ'-Ni3(Al,Ti) (L1_2)"];
    peaks = [
      { twoTheta: 43.6, intensity: 100, hkl: "(111)", phase: "γ-Matrix", fwhm: 0.24 },
      { twoTheta: 50.8, intensity: 48, hkl: "(200)", phase: "γ-Matrix", fwhm: 0.28 },
      { twoTheta: 74.7, intensity: 32, hkl: "(220)", phase: "γ-Matrix", fwhm: 0.32 },
      { twoTheta: 90.7, intensity: 22, hkl: "(311)", phase: "γ-Matrix", fwhm: 0.36 },
      { twoTheta: 46.8, intensity: 15, hkl: "(112)", phase: "γ''-Ni3Nb", fwhm: 0.38 },
      { twoTheta: 35.2, intensity: 8, hkl: "(100)", phase: "MC Carbide", fwhm: 0.35 },
    ];
  } else if (baseMetal === "Ti") {
    crystalSystem = "Hexagonal (HCP)";
    spaceGroup = "P6_3/mmc (194)";
    latticeA = 2.95;
    latticeC = 4.68;
    primaryPhases = ["α-Ti (HCP)", "β-Ti (BCC)"];
    peaks = [
      { twoTheta: 35.1, intensity: 65, hkl: "(100)", phase: "α-Ti (HCP)", fwhm: 0.26 },
      { twoTheta: 38.4, intensity: 78, hkl: "(002)", phase: "α-Ti (HCP)", fwhm: 0.25 },
      { twoTheta: 40.2, intensity: 100, hkl: "(101)", phase: "α-Ti (HCP)", fwhm: 0.28 },
      { twoTheta: 53.0, intensity: 38, hkl: "(102)", phase: "α-Ti (HCP)", fwhm: 0.31 },
      { twoTheta: 39.5, intensity: 42, hkl: "(110)", phase: "β-Ti (BCC)", fwhm: 0.34 },
      { twoTheta: 56.9, intensity: 22, hkl: "(200)", phase: "β-Ti (BCC)", fwhm: 0.36 },
    ];
  } else if (baseMetal === "Al") {
    crystalSystem = "Cubic (FCC)";
    spaceGroup = "Fm-3m (225)";
    latticeA = 4.049;
    primaryPhases = ["α-Al (FCC)", "Si (Diamond)", "Mg2Si (FCC)"];
    peaks = [
      { twoTheta: 38.5, intensity: 100, hkl: "(111)", phase: "α-Al (FCC)", fwhm: 0.22 },
      { twoTheta: 44.7, intensity: 52, hkl: "(200)", phase: "α-Al (FCC)", fwhm: 0.25 },
      { twoTheta: 65.1, intensity: 35, hkl: "(220)", phase: "α-Al (FCC)", fwhm: 0.30 },
      { twoTheta: 78.2, intensity: 28, hkl: "(311)", phase: "α-Al (FCC)", fwhm: 0.34 },
      { twoTheta: 28.4, intensity: 20, hkl: "(111)", phase: "Eutectic Si", fwhm: 0.28 },
    ];
  } else {
    // Steels: Ferrite/Martensite (BCC/BCT) & Austenite (FCC)
    crystalSystem = "Cubic (BCC)";
    spaceGroup = "Im-3m (229)";
    latticeA = 2.866;
    primaryPhases = ["α-Ferrite / Martensite (BCC)", "Fe3C / Alloy Carbides"];
    peaks = [
      { twoTheta: 44.7, intensity: 100, hkl: "(110)", phase: "α-Fe (BCC)", fwhm: 0.25 },
      { twoTheta: 65.0, intensity: 42, hkl: "(200)", phase: "α-Fe (BCC)", fwhm: 0.29 },
      { twoTheta: 82.3, intensity: 55, hkl: "(211)", phase: "α-Fe (BCC)", fwhm: 0.33 },
      { twoTheta: 98.9, intensity: 20, hkl: "(220)", phase: "α-Fe (BCC)", fwhm: 0.38 },
      { twoTheta: 43.5, intensity: 12, hkl: "(111)", phase: "Retained Austenite (γ)", fwhm: 0.36 },
      { twoTheta: 39.8, intensity: 9, hkl: "(121)", phase: "Cementite Fe3C", fwhm: 0.40 },
    ];
  }

  return { crystalSystem, spaceGroup, latticeA_A: latticeA, latticeC_A: latticeC, primaryPhases, peaks };
}

// Convert MaterialSpec into a rich Pipeline Payload
export function createPipelinePayloadFromMaterialSpec(mat: MaterialSpec, sourceModule = "Materials Database"): PipelineMaterialPayload {
  const normComp = normalizeComposition(mat.composition);
  const baseMetal = detectBaseMetal(mat.category, normComp);
  const { profile: kineticProfile, stages: suggestedThermalCycle, icme } = deriveKineticProfile(mat.name, baseMetal, normComp, mat.yieldStrength);
  const { hardnessProfile, hardnessHV, hardnessHVSource, hardnessHRC } = deriveHardnessProfile(
    mat.name,
    mat.category,
    baseMetal,
    mat.yieldStrength,
    mat.tensileStrength,
    mat.youngsModulus,
    mat.elongation,
    mat.hardness,
    mat.microstructure,
    false,
    normComp
  );
  const xrdProfile = deriveXRDProfile(mat.name, baseMetal, normComp);

  return {
    id: mat.id,
    name: mat.name,
    category: mat.category,
    standard: mat.standard,
    sourceModule,
    timestamp: Date.now(),
    composition: normComp,
    compositionUnit: "wt_pct",
    compositionInterpretation: Object.values(mat.composition).some(value => typeof value === "object") ? "range-midpoint" : "nominal",
    originalComposition: mat.composition,
    baseMetal,
    yieldStrength: mat.yieldStrength,
    tensileStrength: mat.tensileStrength,
    youngsModulus: mat.youngsModulus,
    density: mat.density,
    elongation: mat.elongation,
    hardness: mat.hardness,
    hardnessHV,
    hardnessHVSource,
    hardnessHRC,
    poissonsRatio: mat.poissonRatio || (baseMetal === "Al" ? 0.33 : baseMetal === "Ti" ? 0.34 : 0.29),
    thermalConductivity: mat.thermalConductivity,
    microstructure: mat.microstructure,
    kineticProfile,
    suggestedThermalCycle,
    hardnessProfile,
    xrdProfile,
    icmeProfile: icme,
  };
}

// Set Active Pipeline Material in Memory & LocalStorage & Dispatch Event
export function setActivePipelineMaterial(payload: PipelineMaterialPayload): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
  } catch {
    // ignore
  }

  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(EVENT_NAME, { detail: payload }));
  }
}

// Clear Active Pipeline Material
export function clearActivePipelineMaterial(): void {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // ignore
  }

  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(EVENT_NAME, { detail: null }));
  }
}

// Get Active Pipeline Material
export function getActivePipelineMaterial(): PipelineMaterialPayload | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

// Subscribe to Pipeline Material updates
export function subscribeToPipelineMaterial(callback: (payload: PipelineMaterialPayload | null) => void): () => void {
  const handler = (e: Event) => {
    const custom = e as CustomEvent<PipelineMaterialPayload>;
    callback(custom.detail || null);
  };

  if (typeof window !== "undefined") {
    window.addEventListener(EVENT_NAME, handler);
  }

  return () => {
    if (typeof window !== "undefined") {
      window.removeEventListener(EVENT_NAME, handler);
    }
  };
}

// Dispatch Tab Navigation
export function dispatchNavigateToTab(tabId: string): void {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(NAV_EVENT_NAME, { detail: { tabId } }));
  }
}














