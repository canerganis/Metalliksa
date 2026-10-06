/**
 * Metallurgical Unit Conversion & Physical Property Interpretation Engine
 * Compliant with ASTM E140, ISO 18265, ASTM E112, and standard aerospace metallurgy standards.
 */
import { HardnessMaterialClass, NO_TABLE_FOR_CLASS, convertHardness } from "./hardnessConversion";

// ==========================================
// 1. STRESS & PRESSURE CONVERSIONS
// ==========================================
export type StressUnit = "MPa" | "ksi" | "GPa" | "psi" | "bar" | "kgf_mm2" | "N_mm2";

export interface StressConversionState {
  MPa: number;
  ksi: number;
  GPa: number;
  psi: number;
  bar: number;
  kgf_mm2: number;
  N_mm2: number;
}

export function convertStress(value: number, fromUnit: StressUnit): StressConversionState {
  if (isNaN(value) || value === null) {
    value = 0;
  }
  // Base unit is MPa (which equals N/mm^2)
  let mpa = 0;
  switch (fromUnit) {
    case "MPa":
    case "N_mm2":
      mpa = value;
      break;
    case "ksi":
      mpa = value * 6.894757293;
      break;
    case "GPa":
      mpa = value * 1000;
      break;
    case "psi":
      mpa = value * 0.006894757293;
      break;
    case "bar":
      mpa = value * 0.1;
      break;
    case "kgf_mm2":
      mpa = value * 9.80665;
      break;
  }

  return {
    MPa: Number(mpa.toFixed(2)),
    ksi: Number((mpa * 0.1450377377).toFixed(2)),
    GPa: Number((mpa / 1000).toFixed(4)),
    psi: Number((mpa * 145.0377377).toFixed(1)),
    bar: Number((mpa * 10).toFixed(2)),
    kgf_mm2: Number((mpa / 9.80665).toFixed(2)),
    N_mm2: Number(mpa.toFixed(2)),
  };
}

export interface StressInterpretation {
  category: string;
  typicalMaterials: string;
  color: string;
  notes: string;
}

export function interpretStressMpa(mpa: number): StressInterpretation {
  if (mpa <= 120) {
    return {
      category: "Low Strength / High Ductility",
      typicalMaterials: "Pure Annealed Aluminum (1050), Pure Copper, Lead, Solder alloys",
      color: "text-emerald-400",
      notes: "Deformation occurs at low yield points; high elongation and formability.",
    };
  } else if (mpa <= 400) {
    return {
      category: "Structural Mild Steel & Aerospace Al",
      typicalMaterials: "ASTM A36, S275, 1018 Steel, Al 6061-T6, Cartridge Brass",
      color: "text-sky-400",
      notes: "Standard architectural, civil construction, and aerospace skin panels.",
    };
  } else if (mpa <= 850) {
    return {
      category: "High-Strength Structural & Titanium",
      typicalMaterials: "Al 7075-T6, Annealed Ti-6Al-4V, AISI 4130 Normalized, 316L Cold Worked",
      color: "text-indigo-400",
      notes: "Medium-high load airframe components, subsea piping, marine shafts.",
    };
  } else if (mpa <= 1400) {
    return {
      category: "High-Strength Quenched & Tempered / Superalloys",
      typicalMaterials: "AISI 4140/4340 Q&T, 17-4 PH H900, Ti-6Al-4V STA, Inconel 718 Aged",
      color: "text-amber-400",
      notes: "Turbine disks, critical landing gear components, deep-hole drilling collars.",
    };
  } else {
    return {
      category: "Ultra-High Strength / Tool Steels",
      typicalMaterials: "AerMet 100, Maraging 300, 300M Steel, AISI 52100 Bearing Steel, Music Wire",
      color: "text-rose-400",
      notes: "Maximum hardness and load capacity; sensitive to notch brittleness and stress corrosion cracking.",
    };
  }
}

// ==========================================
// 2. HARDNESS
// ==========================================
// Scale conversion lives in ./hardnessConversion (convertSteelHardness: ASTM E140 / ISO 18265 table interpolation,
// shared with Pocket Calculators). Only the qualitative HV band description remains here.

export interface HardnessInterpretation {
  condition: string;
  machinability: string;
  typicalComponent: string;
  wearResistance: string;
}

/**
 * The HV bands are qualitative and written for non-austenitic steels. Only the 450 HV limit has outside support
 * (hard turning is usually taken to start at about 45 HRC, ASTM E140: 45 HRC = 446 HV); the 160, 280 and 750 HV
 * limits are app heuristics without a cited source.
 * Example placement checked against sources (2026-10-04): 300M landing gear is used at 52-55 HRC (Carpenter 300M data
 * sheet; ~545-595 HV per E140), so it sits in the 450-750 band; AISI 4140 normalized at 870 C is 302 HB / 32 HRC
 * (MatWeb), i.e. ~318 HV in the 280-450 band; CBN inserts turn hardened steel up to about 68 HRC (trade sources:
 * Canadian Metalworking, CTE), so >= 750 HV is not "grinding/EDM only". "Solution annealed" is an austenitic/PH term.
 */
export const HARDNESS_INTERPRETATION_NOTE =
  "Qualitative guide for non-austenitic steels only; band limits are approximate (only the ~450 HV / 45 HRC hard-turning limit has outside support), not from a standard.";

export const HARDNESS_INTERPRETATION_UNAVAILABLE =
  "Unavailable: the condition bands are defined for non-austenitic steels only";

/** Qualitative condition for a non-austenitic steel HV; null for every other alloy class (no bands for them). */
export function interpretHardness(hv: number, materialClass: HardnessMaterialClass): HardnessInterpretation | null {
  if (materialClass !== "non-austenitic-steel" || !Number.isFinite(hv)) return null;
  if (hv < 160) {
    return {
      condition: "Dead Soft / Annealed",
      machinability: "Gummy, prone to built-up edge; high rake angle required",
      typicalComponent: "Gaskets, deep-drawn cans, annealed tubing",
      wearResistance: "Low abrasive wear resistance; prone to galling and adhesion",
    };
  } else if (hv < 280) {
    return {
      condition: "Normalized / Stress-Relieved",
      machinability: "Optimal free-machining zone; clean chip breaking",
      typicalComponent: "Drive shafts, structural beams, forged connecting rods",
      wearResistance: "Moderate; suitable for lubricated journal bearings",
    };
  } else if (hv < 450) {
    return {
      condition: "Quenched & Tempered or Normalized Alloy Steel",
      machinability: "Tough cutting; coated carbide or cermet tooling recommended",
      typicalComponent: "High-pressure pump shafts, normalized or Q&T 4140 shafting",
      wearResistance: "High toughness combined with solid impact resistance",
    };
  } else if (hv < 750) {
    return {
      condition: "Fully Hardened / Case Carburized Surface",
      machinability: "Hard turning or grinding only (CBN / ceramic inserts)",
      typicalComponent: "Transmission gears, cam lobes, 300M landing gear, ball bearing races (52100), D2 dies",
      wearResistance: "Exceptional resistance to rolling contact fatigue and abrasive wear",
    };
  } else {
    return {
      condition: "Super-Hard Nitride Case",
      machinability: "CBN hard turning (up to about 68 HRC) or grinding",
      typicalComponent: "Plasma nitrided cylinder liners, valve stems",
      wearResistance: "Extreme sliding abrasive and erosion wear resistance",
    };
  }
}

// ==========================================
// 3. TEMPERATURE & HOMOLOGOUS RATIO
// ==========================================
export type TempUnit = "C" | "K" | "F" | "R";

export interface TempConversionState {
  C: number;
  K: number;
  F: number;
  R: number;
}

export function convertTemperature(val: number, fromUnit: TempUnit): TempConversionState {
  // A non-finite input or a state below absolute zero has no temperature: every scale is NaN (unavailable), never
  // silently 0 K / clamped to 0 K.
  const unavailable: TempConversionState = { C: NaN, K: NaN, F: NaN, R: NaN };
  if (typeof val !== "number" || !Number.isFinite(val)) return unavailable;
  let kelvin = 0;
  switch (fromUnit) {
    case "K":
      kelvin = val;
      break;
    case "C":
      kelvin = val + 273.15;
      break;
    case "F":
      kelvin = (val - 32) * (5 / 9) + 273.15;
      break;
    case "R":
      kelvin = val / 1.8;
      break;
  }

  // Below absolute zero is not a physical state (1e-9 K tolerance keeps -459.67 degF exactly 0 K despite float error).
  if (kelvin < -1e-9) return unavailable;
  kelvin = Math.max(0, kelvin);
  const c = kelvin - 273.15;
  const f = c * (9 / 5) + 32;
  const r = kelvin * 1.8;

  return {
    C: Number(c.toFixed(2)),
    K: Number(kelvin.toFixed(2)),
    F: Number(f.toFixed(2)),
    R: Number(r.toFixed(2)),
  };
}

export interface MeltingPointPreset {
  name: string;
  tmC: number;
  tmK: number;
  crystal: string;
}

export const METALLURGICAL_MELTING_PRESETS: MeltingPointPreset[] = [
  { name: "Iron & Carbon Steels", tmC: 1538, tmK: 1811.15, crystal: "BCC / FCC" },
  { name: "Austenitic Stainless 316L", tmC: 1400, tmK: 1673.15, crystal: "FCC" },
  { name: "Nickel Superalloy (Inconel 718)", tmC: 1330, tmK: 1603.15, crystal: "FCC γ" },
  { name: "Titanium & Ti-6Al-4V", tmC: 1668, tmK: 1941.15, crystal: "HCP α / BCC β" },
  { name: "Aluminum Alloys (6061 / 7075)", tmC: 650, tmK: 923.15, crystal: "FCC" },
  { name: "Pure Copper & Bronzes", tmC: 1085, tmK: 1358.15, crystal: "FCC" },
  { name: "Refractory Tungsten (W)", tmC: 3422, tmK: 3695.15, crystal: "BCC" },
  { name: "Magnesium Alloys (AZ31)", tmC: 650, tmK: 923.15, crystal: "HCP" },
  { name: "Lead Solder (Pb-Sn)", tmC: 183, tmK: 456.15, crystal: "Eutectic" },
];

export interface HomologousInterpretation {
  th: number;
  regime: string;
  deformationMechanism: string;
  color: string;
  recommendation: string;
}

export function calculateHomologousTemperature(
  tempC: number,
  meltingTempC: number
): HomologousInterpretation {
  const tk = tempC + 273.15;
  const tmk = meltingTempC + 273.15;
  const th = Number((tk / tmk).toFixed(3));

  if (th < 0.3) {
    return {
      th,
      regime: "Cold Working (Athermal Plasticity)",
      deformationMechanism: "Dislocation glide dominant; strain hardening without recovery; negligible diffusion.",
      color: "text-sky-400",
      recommendation: "Material work hardens rapidly. Monitor ductile-to-brittle transition temperature (DBTT) in BCC alloys.",
    };
  } else if (th <= 0.5) {
    return {
      th,
      regime: "Warm Working / Recovery Threshold",
      deformationMechanism: "Cross-slip and initial dislocation climb; dynamic recovery onset; subgrain formation.",
      color: "text-amber-400",
      recommendation: "Reduced flow stress with minimal surface scaling. Annealing twins may nucleate in low SFE alloys.",
    };
  } else {
    return {
      th,
      regime: "Hot Working & High-Temperature Creep",
      deformationMechanism: "Dynamic recrystallization; grain boundary sliding; Coble / Nabarro-Herring vacancy creep.",
      color: "text-rose-400",
      recommendation: "High risk of time-dependent creep rupture, grain coarsening, and intergranular oxidation. Creep-resistant alloys required.",
    };
  }
}

// ==========================================
// 4. FRACTURE TOUGHNESS & IMPACT TOUGHNESS
// ==========================================
export type FractureToughnessUnit = "MPa_m05" | "ksi_in05" | "N_mm15" | "MPa_mm05";

export interface FractureToughnessState {
  MPa_m05: number;
  ksi_in05: number;
  N_mm15: number;
  MPa_mm05: number;
}

export function convertFractureToughness(
  value: number,
  fromUnit: FractureToughnessUnit
): FractureToughnessState {
  if (isNaN(value) || value === null) value = 0;
  let mpa_m05 = 0;
  switch (fromUnit) {
    case "MPa_m05":
      mpa_m05 = value;
      break;
    case "ksi_in05":
      mpa_m05 = value * 1.0988434;
      break;
    case "N_mm15":
    case "MPa_mm05":
      mpa_m05 = value / 31.6227766; // sqrt(1000)
      break;
  }

  return {
    MPa_m05: Number(mpa_m05.toFixed(2)),
    ksi_in05: Number((mpa_m05 * 0.9100478).toFixed(2)),
    N_mm15: Number((mpa_m05 * 31.6227766).toFixed(1)),
    MPa_mm05: Number((mpa_m05 * 31.6227766).toFixed(1)),
  };
}

export type ImpactEnergyUnit = "J" | "ft_lbf" | "kgf_m" | "J_cm2";

export interface ImpactEnergyState {
  J: number;
  ft_lbf: number;
  kgf_m: number;
  J_cm2: number;
}

export function convertImpactEnergy(
  value: number,
  fromUnit: ImpactEnergyUnit
): ImpactEnergyState {
  if (isNaN(value) || value === null) value = 0;
  let joules = 0;
  switch (fromUnit) {
    case "J":
      joules = value;
      break;
    case "ft_lbf":
      joules = value * 1.3558179483;
      break;
    case "kgf_m":
      joules = value * 9.80665;
      break;
    case "J_cm2":
      joules = value * 0.8; // standard 10x10mm Charpy ligament = 0.8 cm²
      break;
  }

  return {
    J: Number(joules.toFixed(1)),
    ft_lbf: Number((joules * 0.737562149).toFixed(1)),
    kgf_m: Number((joules / 9.80665).toFixed(2)),
    J_cm2: Number((joules / 0.8).toFixed(1)),
  };
}

// ==========================================
// 5. ASTM E112 GRAIN SIZE & MICRO LENGTHS
// ==========================================
export type LengthUnit = "nm" | "angstrom" | "um" | "mm" | "in" | "mil";

export interface LengthConversionState {
  angstrom: number;
  nm: number;
  um: number;
  mm: number;
  in: number;
  mil: number;
}

export function convertMicroLength(value: number, fromUnit: LengthUnit): LengthConversionState {
  if (isNaN(value) || value === null) value = 0;
  // Base unit: micrometer (um)
  let um = 0;
  switch (fromUnit) {
    case "um":
      um = value;
      break;
    case "nm":
      um = value * 0.001;
      break;
    case "angstrom":
      um = value * 0.0001;
      break;
    case "mm":
      um = value * 1000;
      break;
    case "in":
      um = value * 25400;
      break;
    case "mil":
      um = value * 25.4;
      break;
  }

  return {
    angstrom: Number((um * 10000).toFixed(2)),
    nm: Number((um * 1000).toFixed(3)),
    um: Number(um.toFixed(4)),
    mm: Number((um / 1000).toFixed(6)),
    in: Number((um / 25400).toFixed(7)),
    mil: Number((um / 25.4).toFixed(4)),
  };
}

export interface AstmGrainSizeResult {
  gNumber: number;
  meanInterceptUm: number;
  meanInterceptMm: number;
  grainsPerMm2: number;
  grainsPerSqInch100x: number;
  classification: string;
}

export function calculateAstmE112FromG(g: number): AstmGrainSizeResult {
  const gClamped = Math.max(-3, Math.min(16, g));
  // Mean lineal intercept, the exact inverse of the E112 intercept relation used by calculateAstmE112FromDiameterUm:
  // G = -6.643856 * log10(l_mm) - 3.288  =>  l_mm = 10^(-(G + 3.288) / 6.643856)
  // (Until 2026-10 this was 1000 / sqrt(2^(G+3)) um, a planimetric diameter, so G -> l -> G did not round-trip.)
  const meanInterceptUm = 1000 * Math.pow(10, -(gClamped + 3.288) / 6.643856);
  const grainsPerSqInch100x = Math.pow(2, gClamped - 1);
  const grainsPerMm2 = Math.round(grainsPerSqInch100x * 15.5);

  let classification = "Fine Grain";
  if (gClamped < 5) classification = "Coarse Grain (Low toughness, high hardenability)";
  else if (gClamped <= 8) classification = "Standard Fine Grain (Balanced yield strength & toughness)";
  else if (gClamped <= 12) classification = "Ultra-Fine Grain (Hall-Petch strengthened, high fatigue life)";
  else classification = "Sub-Micron / Nanocrystalline (High strength, low thermal stability)";

  return {
    gNumber: Number(gClamped.toFixed(1)),
    meanInterceptUm: Number(meanInterceptUm.toFixed(2)),
    meanInterceptMm: Number((meanInterceptUm / 1000).toFixed(4)),
    grainsPerMm2,
    grainsPerSqInch100x: Number(grainsPerSqInch100x.toFixed(1)),
    classification,
  };
}

export function calculateAstmE112FromDiameterUm(diameterUm: number): AstmGrainSizeResult {
  const d = Math.max(0.5, Math.min(2000, diameterUm));
  // G = -6.643856 * log10(d_mm) - 3.288
  const dMm = d / 1000;
  const g = -6.643856 * Math.log10(dMm) - 3.288;
  return calculateAstmE112FromG(g);
}

// ==========================================
// 6. CORROSION PENETRATION RATE
// ==========================================
export type CorrosionRateUnit = "mm_yr" | "mpy" | "um_yr" | "nm_day" | "g_m2_day";

export interface CorrosionRateState {
  mm_yr: number;
  mpy: number;
  um_yr: number;
  nm_day: number;
  g_m2_day: number; // for mild steel
  naceRating: string;
  naceColor: string;
}

export function convertCorrosionRate(
  value: number,
  fromUnit: CorrosionRateUnit,
  densityGcm3: number = 7.85 // standard carbon steel density
): CorrosionRateState {
  if (isNaN(value) || value === null) value = 0;
  // Base unit: mm/year
  let mm_yr = 0;
  switch (fromUnit) {
    case "mm_yr":
      mm_yr = value;
      break;
    case "mpy":
      mm_yr = value * 0.0254;
      break;
    case "um_yr":
      mm_yr = value * 0.001;
      break;
    case "nm_day":
      mm_yr = (value * 365.25) / 1e6;
      break;
    case "g_m2_day":
      // Faraday / mass loss formula: CR (mm/yr) = 365.25 * MDD / (10 * density) = 36.525 * MDD / (10 * density)
      // Actually: 1 g/(m²·day) -> 365 g/(m²·yr) -> volume = 365 / (density * 1e6) m³/yr -> thickness = 365 / (density * 1e6 * 1) m/yr = 0.365 / density mm/yr
      mm_yr = (0.365 * value) / densityGcm3;
      break;
  }

  const mpy = mm_yr * 39.37007874;
  const um_yr = mm_yr * 1000;
  const nm_day = (mm_yr * 1e6) / 365.25;
  const g_m2_day = (mm_yr * densityGcm3) / 0.365;

  let naceRating = "Acceptable";
  let naceColor = "text-sky-400";
  if (mpy < 1) {
    naceRating = "Outstanding (< 1 mpy / < 0.025 mm/yr) — Excellent corrosion resistance; minimal thinning.";
    naceColor = "text-emerald-400";
  } else if (mpy <= 5) {
    naceRating = "Good (1 - 5 mpy / 0.025 - 0.125 mm/yr) — Generally acceptable for equipment with corrosion allowance.";
    naceColor = "text-sky-400";
  } else if (mpy <= 20) {
    naceRating = "Fair / Moderate (5 - 20 mpy / 0.125 - 0.5 mm/yr) — Frequent inspection required; coating or inhibitors needed.";
    naceColor = "text-amber-400";
  } else {
    naceRating = "Unacceptable (> 20 mpy / > 0.5 mm/yr) — Rapid metal loss, wall thinning, risk of catastrophic puncture.";
    naceColor = "text-rose-400";
  }

  return {
    mm_yr: Number(mm_yr.toFixed(4)),
    mpy: Number(mpy.toFixed(2)),
    um_yr: Number(um_yr.toFixed(2)),
    nm_day: Number(nm_day.toFixed(2)),
    g_m2_day: Number(g_m2_day.toFixed(2)),
    naceRating,
    naceColor,
  };
}

// ==========================================
// 7. DENSITY & THERMAL / ELECTRICAL
// ==========================================
export interface DensityConversionState {
  g_cm3: number;
  kg_m3: number;
  lb_in3: number;
  lb_ft3: number;
}

export function convertDensity(
  value: number,
  fromUnit: "g_cm3" | "kg_m3" | "lb_in3" | "lb_ft3"
): DensityConversionState {
  if (isNaN(value) || value === null) value = 0;
  let g_cm3 = 0;
  switch (fromUnit) {
    case "g_cm3":
      g_cm3 = value;
      break;
    case "kg_m3":
      g_cm3 = value / 1000;
      break;
    case "lb_in3":
      g_cm3 = value / 0.036127292;
      break;
    case "lb_ft3":
      g_cm3 = value / 62.42796;
      break;
  }

  return {
    g_cm3: Number(g_cm3.toFixed(3)),
    kg_m3: Number((g_cm3 * 1000).toFixed(1)),
    lb_in3: Number((g_cm3 * 0.036127292).toFixed(5)),
    lb_ft3: Number((g_cm3 * 62.42796).toFixed(2)),
  };
}

// ==========================================
// 8. DUAL-UNIT TEST REPORT SCRATCHPAD (SI -> US customary + hardness)
// ==========================================
export type ReportHardnessScale = "HRC" | "HV" | "HBW" | "HRB";

export interface DualUnitReportInputs {
  yieldMpa: number;
  utsMpa: number;
  /** Measured hardness value and the scale it was measured in (reported as the primary value). */
  hardnessValue: number;
  hardnessScale: ReportHardnessScale;
  /** Only "non-austenitic-steel" is converted (ASTM E140 tables); other classes report the measured value only. */
  hardnessMaterialClass: HardnessMaterialClass;
  cvnJ: number;
  testTempC: number;
}

export interface DualUnitReport {
  yieldKsi: number;
  utsKsi: number;
  /** Measured hardness, e.g. "34 HRC". */
  hardnessMeasured: string;
  /** Converted estimates of the other scales, e.g. "≈ 336 HV / 319 HBW"; null when none is available. */
  hardnessConverted: string | null;
  /** Measured value with the converted estimate (or the reason it is unavailable) in parentheses. */
  hardnessText: string;
  /** Converted values (null = unavailable); the measured scale echoes the input. */
  hrc: number | null;
  hv: number | null;
  hbw: number | null;
  cvnFtLbf: number;
  tempF: number;
  tempK: number;
}

const REPORT_HARDNESS_ORDER: ReportHardnessScale[] = ["HRC", "HV", "HBW"];

/** Hardness line of the copied report: no placeholder value when no measured hardness was entered (e.g. after a load). */
export function reportHardnessLine(entered: boolean, hardnessText: string, syncNote: string | null): string {
  if (entered) return hardnessText;
  return syncNote ? `not entered (${syncNote})` : "not entered";
}

export function computeDualUnitReport(inputs: DualUnitReportInputs): DualUnitReport {
  const { yieldMpa: reportYieldMpa, utsMpa: reportUtsMpa, cvnJ: reportCvnJ, testTempC: reportTestTempC } = inputs;
  const yieldKsi = Number((reportYieldMpa * 0.1450377).toFixed(1));
  const utsKsi = Number((reportUtsMpa * 0.1450377).toFixed(1));
  const hState = convertHardness(inputs.hardnessValue, inputs.hardnessScale, inputs.hardnessMaterialClass);
  const hardnessMeasured = `${inputs.hardnessValue} ${inputs.hardnessScale}`;
  const parts = REPORT_HARDNESS_ORDER.filter((sc) => sc !== inputs.hardnessScale)
    .map((sc) => (hState[sc] === null ? null : `${hState[sc]} ${sc}`))
    .filter((t): t is string => t !== null);
  const hardnessConverted = parts.length > 0 ? `≈ ${parts.join(" / ")}` : null;
  const reason =
    inputs.hardnessMaterialClass === "non-austenitic-steel" ? "outside the verified table range" : NO_TABLE_FOR_CLASS.replace(/^Unavailable: /, "");
  const hardnessText =
    hardnessConverted === null
      ? `${hardnessMeasured} (converted values: Unavailable, ${reason})`
      : `${hardnessMeasured} (${hardnessConverted}, converted per ASTM E140 tables, not measured)`;
  const cvnFtLbf = Number((reportCvnJ * 0.737562).toFixed(1));
  const tempF = Number((reportTestTempC * 1.8 + 32).toFixed(1));
  const tempK = Number((reportTestTempC + 273.15).toFixed(1));
  return {
    yieldKsi,
    utsKsi,
    hardnessMeasured,
    hardnessConverted,
    hardnessText,
    hrc: hState.HRC,
    hv: hState.HV,
    hbw: hState.HBW,
    cvnFtLbf,
    tempF,
    tempK,
  };
}
