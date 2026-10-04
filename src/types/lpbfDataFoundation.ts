/**
 * LPBF GROUND TRUTH & DATA FOUNDATION SCHEMA
 * 
 * Strict 5-tier relational data hierarchy:
 * Build ──> ProcessParams ──> Sample ──> Properties ──> Source
 * 
 * Includes rigorous derived energy metrics:
 * - Linear Energy Density (LED): E_L = P / v [J/mm]
 * - Areal / Surface Energy Density (AED): E_A = P / (v · h) [J/mm²]
 * - Volumetric Energy Density (VED): E_V = P / (v · h · t) [J/mm³]
 * 
 * Fully documents and calculates the recognized physical limitations of VED.
 */
import { authorityThermal } from "../data/lpbfMaterialAuthority";

export type LPBFAlloyId = "ti6al4v" | "ss316l" | "alsi10mg" | "in718" | "in625";
export type ProcessRegime = 
  | "Lack of Fusion (LoF)"
  | "Stable Conduction"
  | "Keyhole Vaporization"
  | "Balling / Plateau-Rayleigh Instability";

export type ScanStrategy = 
  | "Meander (67° alternating rotation)"
  | "Stripe (5mm width, 90° rotation)"
  | "Island / Checkerboard (5x5mm)"
  | "Unidirectional Continuous"
  | "Bidirectional (0°/90°)";

export type HeatTreatmentCondition = 
  | "As-Built"
  | "Stress Relieved (SR)"
  | "Hot Isostatic Pressed (HIP)"
  | "Solution Treated & Aged (STA)"
  | "Annealed";

export type DensityMethod = 
  | "Archimedes (ASTM B962)"
  | "Optical Microscopy Image Analysis (ASTM E1245)"
  | "X-ray Micro-Computed Tomography (Micro-CT)";

export interface SourceCitation {
  id: string;
  sourceType: "literature" | "experimental" | "internal_qualification";
  citation: string;
  title: string;
  authors: string;
  journal: string;
  year: number;
  doi: string;
  url?: string;
  testingStandards: string[]; // e.g. ["ASTM B962", "ASTM E8/E8M", "ASTM E384"]
  labOrganization: string;
}

export interface LPBFProcessParams {
  id: string;
  laserPower_W: number;          // P [W]
  scanSpeed_mm_s: number;        // v [mm/s]
  hatchSpacing_um: number;       // h [µm]
  layerThickness_um: number;     // t [µm]
  beamSpotDiameter_um: number;   // d_spot or 2*w0 [µm]
  scanStrategy: ScanStrategy;
  baseplatePreheat_C: number;
  chamberAtmosphere: string;     // e.g. "Argon 99.999% (<100 ppm O2)"
  opticalAbsorptivity: number;   // η (0.3 - 0.7 depending on material and wavelength)

  // Derived Quantities (rigorously calculated)
  derived: {
    linearEnergyDensity_J_mm: number;      // E_L = P / v [J/mm]
    arealEnergyDensity_J_mm2: number;      // E_A = P / (v * h) [J/mm²]
    volumetricEnergyDensity_J_mm3: number; // E_V = P / (v * h * t) [J/mm³]
    peakLaserIntensity_MW_cm2: number;     // I_0 = 4P / (pi * d^2) [MW/cm²]
    normalizedEnthalpy_dH_hs?: number;     // Normalized Enthalpy (King et al.)
    pecletNumber?: number;                 // Pe = v * d / (2 * alpha)
    predictedRegime: ProcessRegime;
  };
}

export interface LPBFSample {
  id: string;
  sampleCode: string;            // e.g. "TI64-THIJS-S04", "316L-EXP-08"
  locationOnPlate: {
    x_mm: number;
    y_mm: number;
    z_mm: number;
  };
  buildOrientationDeg: 0 | 45 | 90; // 0 = Horizontal, 90 = Vertical
  heatTreatment: HeatTreatmentCondition;
  specimenGeometry: "Cylindrical Tensile (ASTM E8)" | "Flat Dogbone" | "Cubic Density (10x10x10mm)" | "Charpy Impact" | "Metallographic Coupon";
}

export interface LPBFMeasuredProperties {
  id: string;
  relativeDensity_pct: number;       // e.g. 99.85 %
  porosity_pct: number;              // e.g. 0.15 %
  densityMeasurementMethod: DensityMethod;
  yieldStrength_MPa?: number;        // Rp0.2 [MPa]
  ultimateTensileStrength_MPa?: number; // Rm / UTS [MPa]
  elongationAtBreak_pct?: number;    // A [%]
  reductionOfArea_pct?: number;      // Z [%]
  hardness_value?: number;
  hardness_scale?: "HV0.3" | "HV0.5" | "HV1" | "HV5" | "HV10" | "HRC";
  youngsModulus_GPa?: number;
  fatigueLimit_MPa?: number; // Runout screening at ~10^7 cycles when reported (ASTM E466 / equivalent)
  defectMorphology?: "Dense (<0.1% pores)" | "Lack of Fusion (irregular, un-melted powder)" | "Keyhole Pores (spherical, root of melt pool)" | "Gas Porosity / Balling";
  microstructureDescription?: string;
}

export interface LPBFBuild {
  id: string;
  buildJobName: string;
  alloyId: LPBFAlloyId;
  alloyName: string;
  machineModel: string;              // e.g. "EOS M290", "SLM Solutions 280HL", "Renishaw RenAM 500Q"
  powderLotNumber: string;
  powderAtomization: "Gas Atomized (GA)" | "Plasma Atomized (PA)" | "PREP";
  powderD10_um: number;
  powderD50_um: number;              // Median particle size [µm]
  powderD90_um: number;
  buildDate: string;
  facility: string;
  notes?: string;
}

/**
 * Unified Traceable Record connecting the full 5-tier backbone:
 * Build -> ProcessParams -> Sample -> Properties -> Source
 */
export interface TraceableLPBFRecord {
  id: string;
  build: LPBFBuild;
  params: LPBFProcessParams;
  sample: LPBFSample;
  properties: LPBFMeasuredProperties;
  source: SourceCitation;
}

/**
 * Physical Constants for Energy Density & Normalized Enthalpy calculations
 */
export interface AlloyThermalConstants {
  meltingPoint_C: number;
  density_kg_m3: number;
  specificHeat_J_kgK: number;
  thermalConductivity_W_mK: number;
  thermalDiffusivity_m2_s: number;
  enthalpyOfMelting_hs_J_m3: number; // rho * Cp * Tm (enthalpy per unit volume to reach melting)
  defaultAbsorptivity: number;
  lofVedThreshold_J_mm3: number;
  keyholeVedThreshold_J_mm3: number;
}

/**
 * TS-local, not authority: VED regime thresholds used only by classifyProcessRegime.
 * The Python material authority has no counterpart for these values.
 */
const VED_REGIME_THRESHOLDS_TS_LOCAL: Record<LPBFAlloyId, { lof_J_mm3: number; keyhole_J_mm3: number }> = {
  ti6al4v: { lof_J_mm3: 48, keyhole_J_mm3: 110 },
  ss316l: { lof_J_mm3: 55, keyhole_J_mm3: 135 },
  alsi10mg: { lof_J_mm3: 40, keyhole_J_mm3: 95 },
  in718: { lof_J_mm3: 52, keyhole_J_mm3: 125 },
  in625: { lof_J_mm3: 50, keyhole_J_mm3: 110 },
};

/**
 * Material constants read from the Python authority (src/generated/lpbfMaterialAuthority.json):
 * Tm = liquidus_C, rho, Cp and k are the solid rows, defaultAbsorptivity = absorptivity_IR.
 * alpha = k / (rho Cp) and h_s = rho Cp Tm are derived here from those values; no alloy number is held in TS.
 */
function alloyThermalConstantsFromAuthority(alloyId: LPBFAlloyId): AlloyThermalConstants {
  const t = authorityThermal(alloyId);
  const rho = t.density_kg_m3;
  const cp = t.specific_heat_J_kgK;
  const k = t.thermal_conductivity_W_mK;
  const thresholds = VED_REGIME_THRESHOLDS_TS_LOCAL[alloyId];
  return {
    meltingPoint_C: t.liquidus_C,
    density_kg_m3: rho,
    specificHeat_J_kgK: cp,
    thermalConductivity_W_mK: k,
    thermalDiffusivity_m2_s: k / (rho * cp),
    enthalpyOfMelting_hs_J_m3: rho * cp * t.liquidus_C,
    defaultAbsorptivity: t.absorptivity_IR,
    lofVedThreshold_J_mm3: thresholds.lof_J_mm3,
    keyholeVedThreshold_J_mm3: thresholds.keyhole_J_mm3,
  };
}

export const ALLOY_THERMAL_PROPERTIES: Readonly<Record<LPBFAlloyId, AlloyThermalConstants>> = Object.freeze({
  ti6al4v: alloyThermalConstantsFromAuthority("ti6al4v"),
  ss316l: alloyThermalConstantsFromAuthority("ss316l"),
  alsi10mg: alloyThermalConstantsFromAuthority("alsi10mg"),
  in718: alloyThermalConstantsFromAuthority("in718"),
  in625: alloyThermalConstantsFromAuthority("in625"),
});

/** Constants for a known alloy id; an unknown id throws (no surrogate alloy is substituted). */
export function alloyThermalConstants(alloyId: LPBFAlloyId): AlloyThermalConstants {
  if (!Object.prototype.hasOwnProperty.call(ALLOY_THERMAL_PROPERTIES, alloyId)) {
    throw new Error(`Unknown LPBF alloy "${String(alloyId)}": thermal constants unavailable; no surrogate alloy is substituted.`);
  }
  return ALLOY_THERMAL_PROPERTIES[alloyId];
}

/**
 * Standard Derived Energy Quantities
 */

/** Linear Energy Density: E_L = P / v [J/mm] */
export function calculateLinearEnergyDensity(power_W: number, scanSpeed_mm_s: number): number {
  if (scanSpeed_mm_s <= 0) return 0;
  return Number((power_W / scanSpeed_mm_s).toFixed(3));
}

/** Areal / Surface Energy Density: E_A = P / (v * h) [J/mm²] (where h is in mm) */
export function calculateArealEnergyDensity(
  power_W: number,
  scanSpeed_mm_s: number,
  hatchSpacing_um: number
): number {
  const hatch_mm = hatchSpacing_um / 1000;
  if (scanSpeed_mm_s <= 0 || hatch_mm <= 0) return 0;
  return Number((power_W / (scanSpeed_mm_s * hatch_mm)).toFixed(3));
}

/** Volumetric Energy Density: E_V = P / (v * h * t) [J/mm³] (where h and t are converted to mm) */
export function calculateVolumetricEnergyDensity(
  power_W: number,
  scanSpeed_mm_s: number,
  hatchSpacing_um: number,
  layerThickness_um: number
): number {
  const hatch_mm = hatchSpacing_um / 1000;
  const layer_mm = layerThickness_um / 1000;
  if (scanSpeed_mm_s <= 0 || hatch_mm <= 0 || layer_mm <= 0) return 0;
  return Number((power_W / (scanSpeed_mm_s * hatch_mm * layer_mm)).toFixed(2));
}

/** Gaussian peak irradiance for a 1/e² diameter: I_0 = 8P / (pi * d_spot^2) [MW/cm²]. */
export function calculatePeakLaserIntensity(power_W: number, beamDiameter_um: number): number {
  if (beamDiameter_um <= 0) return 0;
  const radius_cm = (beamDiameter_um / 2) * 1e-4; // µm to cm
  const area_cm2 = Math.PI * Math.pow(radius_cm, 2);
  const power_MW = power_W * 1e-6;
  return Number(((2 * power_MW) / area_cm2).toFixed(3));
}

/**
 * Normalized Enthalpy (King / Gouge / Scime criterion): ΔH / h_s
 * Constants come from the Python authority; an unknown alloy throws. This annotation uses
 * h_s = rho Cp Tm(°C); python/lpbf_thermal_solver.py uses rho Cp max(50, T_liq - T_preheat)
 * with a powder-bed absorptivity, so the two are not the same number.
 */
export function calculateNormalizedEnthalpy(
  power_W: number,
  scanSpeed_mm_s: number,
  beamDiameter_um: number,
  alloyId: LPBFAlloyId,
  absorptivity?: number
): number {
  const alloy = alloyThermalConstants(alloyId);
  const eta = absorptivity !== undefined ? absorptivity : alloy.defaultAbsorptivity;
  const v_m_s = scanSpeed_mm_s * 1e-3;
  const sigma_m = (beamDiameter_um / 2) * 1e-6; // beam radius in meters
  const alpha = alloy.thermalDiffusivity_m2_s;
  const hs = alloy.enthalpyOfMelting_hs_J_m3;

  // delta H / hs ~ (eta * P) / (hs * sqrt(pi * alpha * v * sigma^3))
  const denominator = hs * Math.sqrt(Math.PI * alpha * Math.max(1e-4, v_m_s) * Math.pow(Math.max(1e-6, sigma_m), 3));
  if (denominator <= 0) return 0;
  const normalized = (eta * power_W) / denominator;
  return Number(normalized.toFixed(2));
}

/**
 * Classify Process Regime based on VED, laser power, speed and alloy thresholds
 */
export function classifyProcessRegime(
  ved_J_mm3: number,
  power_W: number,
  scanSpeed_mm_s: number,
  alloyId: LPBFAlloyId
): ProcessRegime {
  const alloy = alloyThermalConstants(alloyId);

  // Balling occurs when scan speed is excessively high with insufficient linear density
  const linearDensity = power_W / Math.max(1, scanSpeed_mm_s);
  if (scanSpeed_mm_s > 1500 && linearDensity < 0.12) {
    return "Balling / Plateau-Rayleigh Instability";
  }

  if (ved_J_mm3 < alloy.lofVedThreshold_J_mm3) {
    return "Lack of Fusion (LoF)";
  } else if (ved_J_mm3 > alloy.keyholeVedThreshold_J_mm3) {
    return "Keyhole Vaporization";
  } else {
    return "Stable Conduction";
  }
}

/**
 * Geometric LoF gates (Tang et al.):
 * Tang index (h/W)^2+(t/D)^2 ≤ 1 for consolidation; also report W/h and D/t.
 */
export function classifyHatchLayerOverlap(
  meltPoolWidth_um: number,
  meltPoolDepth_um: number,
  hatchSpacing_um: number,
  layerThickness_um: number
): {
  hatchOverlapFail: boolean;
  layerOverlapFail: boolean;
  widthOverHatch: number;
  depthOverLayer: number;
  tangIndex: number;
  status: "Pass" | "Warning" | "Fail";
} {
  const widthOverHatch = meltPoolWidth_um / Math.max(1, hatchSpacing_um);
  const depthOverLayer = meltPoolDepth_um / Math.max(1, layerThickness_um);
  const hOverW = hatchSpacing_um / Math.max(1, meltPoolWidth_um);
  const tOverD = layerThickness_um / Math.max(1, meltPoolDepth_um);
  const tangIndex = hOverW * hOverW + tOverD * tOverD;
  const hatchOverlapFail = hatchSpacing_um > meltPoolWidth_um;
  const layerOverlapFail = layerThickness_um > meltPoolDepth_um;
  let status: "Pass" | "Warning" | "Fail" = "Pass";
  if (tangIndex > 1.0 || hatchOverlapFail || layerOverlapFail) status = "Fail";
  else if (tangIndex > 0.8) status = "Warning";
  return { hatchOverlapFail, layerOverlapFail, widthOverHatch, depthOverLayer, tangIndex, status };
}
