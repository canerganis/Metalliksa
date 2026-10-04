export interface TafelRawPoint {
  index: number;
  potential: number; // V vs Reference electrode
  potentialSHE?: number; // V vs Standard Hydrogen Electrode
  currentRaw: number; // Raw current from instrument (A, mA, uA)
  currentUnit: "A" | "mA" | "uA" | "nA";
  currentDensity_uA_cm2: number; // Absolute current density in uA/cm2
  logCurrentDensity: number; // log10(abs(currentDensity_uA_cm2))
  signedCurrentDensity_uA_cm2: number; // signed (+ for anodic, - for cathodic)
  isCathodic?: boolean; // E < Ecorr
  isAnodic?: boolean; // E > Ecorr
}

export type ReferenceElectrodeType =
  | "SHE" // Standard Hydrogen Electrode (0.000 V)
  | "SCE" // Saturated Calomel Electrode (+0.241 V vs SHE)
  | "Ag/AgCl" // Saturated KCl (+0.197 V vs SHE)
  | "MSE" // Mercury-Mercurous Sulfate (+0.640 V vs SHE)
  | "Custom";

export interface TafelDataset {
  id: string;
  name: string;
  sourceFilename: string;
  sourceInstrument: "biologic" | "gamry" | "autolab" | "par" | "csv" | "benchmark";
  points: TafelRawPoint[];
  metadata: {
    electrodeAreaCm2: number;
    referenceElectrode: ReferenceElectrodeType;
    refOffsetVsSHE: number; // e.g. 0.241 for SCE
    alloyName: string;
    density_g_cm3: number;
    equivalentWeight: number; // g / eq
    electrolyte: string;
    temperatureC: number;
    scanRateMv_s?: number;
    notes?: string;
  };
}

/**
 * Tafel fit result. A value is null when it is unavailable: a Tafel branch with too few points or a
 * wrong-sign slope has no slope, beta or R2; without both branches there is no Evans intersection
 * (Ecorr/icorr) and nothing derived from it. Unavailable values are never replaced by an assumed
 * slope, R2 or current (the former beta_a = 100 mV/dec with R2 = 0.85 fallback is gone). The UI shows
 * null as "Unavailable" with `unavailableReason`; see src/utils/tafelDisplay.ts.
 * `fitStatus` is absent on a complete fit.
 */
export interface TafelFitResult {
  fitStatus?: "ok" | "unavailable";
  unavailableReason?: string;
  /** Per-item reasons: anodicBranch / cathodicBranch / iCorr_uA_cm2 / substrate. */
  unavailable?: Partial<Record<"anodicBranch" | "cathodicBranch" | "iCorr_uA_cm2" | "substrate", string>>;

  // Primary Extrapolated Coordinates
  eCorr: number | null; // Extrapolated Corrosion Potential (V vs Ref)
  eCorrSHE: number | null; // Corrosion Potential vs SHE (V)
  iCorr_uA_cm2: number | null; // Extrapolated Corrosion Current Density (uA/cm2)
  logIcorr: number | null; // log10(iCorr_uA_cm2)
  totalCurrentIcorr_uA: number | null; // iCorr * Area (uA)

  // Slopes and Coefficients
  betaA_V_dec: number | null; // Anodic Tafel slope (V/decade)
  betaA_mV_dec: number | null; // Anodic Tafel slope (mV/decade)
  betaC_V_dec: number | null; // Cathodic Tafel slope (V/decade)
  betaC_mV_dec: number | null; // Cathodic Tafel slope (mV/decade)
  sternGearyB_V: number | null; // B constant (V)
  rp_ohm_cm2: number | null; // Polarization resistance Rp (Ohm * cm2)

  // Faraday Corrosion Rates (ASTM G102)
  corrosionRateMmYr: number | null; // Penetration rate (mm/year)
  corrosionRateMpy: number | null; // Mils per year (mpy)
  massLoss_g_m2_day: number | null; // g / (m2 * day)

  // Fit Quality and Ranges
  cathodicRange: [number, number]; // [E_min, E_max] in V
  anodicRange: [number, number]; // [E_min, E_max] in V
  cathodicR2: number | null; // R-squared of cathodic Tafel fit
  anodicR2: number | null; // R-squared of anodic Tafel fit
  cathodicSlope_m: number | null; // d(log i) / dE (1 / V)
  cathodicIntercept_b: number | null; // Intercept
  anodicSlope_m: number | null; // d(log i) / dE (1 / V)
  anodicIntercept_b: number | null; // Intercept

  // Raw Valley Benchmark
  rawEcorrValley: number; // Potential of minimum measured current (V)
  rawIcorrValley: number; // Minimum measured current density (uA/cm2)

  // Tangents & Butler-Volmer Model Data for Charting
  tangentLines: {
    potential: number;
    logI_anodic?: number | null;
    logI_cathodic?: number | null;
  }[];
  syntheticButlerVolmer: {
    potential: number;
    logI_model: number;
  }[];

  // Passivity & Pitting if Detected
  pittingPotentialEpit_V?: number | null;
  passivationCurrentIpass_uA?: number | null;

  // Severity and Assessment (null when no corrosion rate is available)
  severity: "Immune / Highly Resistant" | "Passivated / Good" | "Moderate (Caution)" | "Severe Rapid Corrosion" | null;
  astmClassification: string | null;

  // Python Engine Provenance
  isPythonEngine?: boolean;
  pythonVersion?: string;
  durationMs?: number;
}

/** The nullable fit values, all present: what a complete Tafel fit (both branches, i_corr known) carries. */
export type TafelFitCompleteKeys =
  | "eCorr" | "eCorrSHE" | "iCorr_uA_cm2" | "logIcorr" | "totalCurrentIcorr_uA"
  | "betaA_V_dec" | "betaA_mV_dec" | "betaC_V_dec" | "betaC_mV_dec" | "sternGearyB_V" | "rp_ohm_cm2"
  | "corrosionRateMmYr" | "corrosionRateMpy" | "massLoss_g_m2_day"
  | "cathodicR2" | "anodicR2" | "cathodicSlope_m" | "cathodicIntercept_b" | "anodicSlope_m" | "anodicIntercept_b"
  | "severity" | "astmClassification";

export type TafelFitComplete = Omit<TafelFitResult, TafelFitCompleteKeys> & {
  [K in TafelFitCompleteKeys]-?: NonNullable<TafelFitResult[K]>;
};

export interface TafelPythonCorrosionRateInput {
  /** Required measurement: omit it (or send null) and the engine reports the rate as unavailable. */
  iCorr_uA_cm2?: number | null;
  eCorr_V?: number | null;
  /** Without both slopes the Stern-Geary B and Rp are unavailable; the Faraday rate does not need them. */
  betaA?: number | null;
  betaC?: number | null;
  alloyId?: string;
  alloyName?: string;
  density_g_cm3?: number;
  equivalentWeight?: number;
  specimenAreaCm2?: number;
  initialThicknessMm?: number;
  allowableLossMm?: number;
  temperatureC?: number;
  activationEnergyJ_mol?: number;
  customComposition?: Record<string, number>;
  customValencies?: Record<string, number>;
  customAtomicWeights?: Record<string, number>;
}

export interface TafelYearlyProjection {
  year: number;
  lossUniformMm: number;
  lossPittingMm: number;
  remainingWallMm: number;
  remainingPittingMm: number;
  wallLossPct: number;
  exceedsAllowance: boolean;
}

export interface TafelTemperatureSensitivity {
  tempC: number;
  tempK: number;
  arrheniusFactor: number;
  iCorr_uA_cm2: number;
  corrosionRateMmYr: number;
  corrosionRateMpy: number;
}

/**
 * Annual corrosion-rate engine result (python/tafel_corrosion_rate_solver.py solve_tafel_corrosion_rate).
 * status "unavailable": the corrosion current density iCorr_uA_cm2 was missing or invalid, so every rate, loss and
 * projection is null/empty (nothing is invented; unavailableReason says why). status "partial": betaA and/or betaC
 * were not supplied, so only sternGearyB_V and rp_* are null. No status: complete.
 */
export interface TafelPythonCorrosionRateResult {
  success: boolean;
  status?: "partial" | "unavailable";
  unavailableReason?: string;
  unavailable?: Record<string, string>;
  isPythonEngine: boolean;
  pythonVersion?: string;
  standards?: string[];
  durationMs?: number;
  timestamp?: string;

  // Primary Rates (null when status is "unavailable")
  corrosionRateMmYr: number | null; // Primary annual rate in mm/year
  corrosionRateMpy: number | null; // mils per year
  corrosionRateUmYr: number | null; // um/year
  corrosionRateNmHr: number | null; // nm/hour
  massLoss_g_m2_day: number | null; // g / (m^2 * day)
  massLoss_mdd: number | null; // mg / (dm^2 * day)
  massLoss_kg_m2_yr: number | null; // kg / (m^2 * year)

  // Stern-Geary Metrics (null when betaA/betaC were not supplied)
  sternGearyB_V: number | null;
  rp_ohm_cm2: number | null;
  rp_apparent_ohm: number | null;

  // Substrate Metadata
  alloyId: string;
  alloyName: string;
  density_g_cm3: number;
  equivalentWeight: number;
  iCorr_uA_cm2: number | null;
  eCorr_V: number | null;
  betaA: number | null;
  betaC: number | null;
  specimenAreaCm2: number;
  temperatureC: number;
  initialThicknessMm: number;
  allowableLossMm: number;

  // Remaining Useful Life (RUL)
  rulUniformYears: number | null;
  rulPittingYears: number | null;

  // Severity Classification (null when unavailable)
  severity: {
    level: string;
    code: string;
    color: "emerald" | "sky" | "amber" | "orange" | "rose";
    description: string;
    recommendation: string;
  } | null;

  // Timeline Projections & Temperature Variations
  timelineProjections: TafelYearlyProjection[];
  temperatureSensitivity: TafelTemperatureSensitivity[];

  // Reproducible Python Snippet (null when unavailable)
  pythonCode: string | null;
  error?: string;
}
